from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from rest_framework import status
from rest_framework.test import APIClient
from django.test import TestCase

from .models import (
    Friendship, QuizChallenge, Document, Question,
    TestSession, SessionResponse, DailyQuiz, DailyQuizSession,
)


def make_user(username):
    user = User.objects.create_user(
        username, email=f'{username}@example.com', password='StrongPass1!'
    )
    return user


def make_friends(a, b):
    return Friendship.objects.create(
        sender=a, receiver=b, initiator=a, status=Friendship.Status.ACCEPTED
    )


class SocialApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _as(self, user):
        self.client.force_authenticate(user=user)
        return self.client

    # ── Request lifecycle ──────────────────────────────────────

    def test_send_list_accept_friendship(self):
        alice, bob = make_user('alice'), make_user('bob')

        res = self._as(alice).post('/api/social/request/send/', {'user_id': bob.pk})
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Bob sees it incoming; alice sees it outgoing
        bob_req = self._as(bob).get('/api/social/requests/')
        self.assertEqual(bob_req.data['incoming'][0]['friend']['username'], 'alice')
        alice_req = self._as(alice).get('/api/social/requests/')
        self.assertEqual(alice_req.data['outgoing'][0]['friend']['username'], 'bob')

        # Duplicate send is rejected (no double rows)
        dup = self._as(alice).post('/api/social/request/send/', {'user_id': bob.pk})
        self.assertEqual(dup.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Friendship.objects.count(), 1)

        # Bob accepts → symmetrical friend lists
        pk = bob_req.data['incoming'][0]['id']
        res = self._as(bob).post(
            f'/api/social/request/{pk}/respond/', {'action': 'accept'}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        for who in (alice, bob):
            friends = self._as(who).get('/api/social/friends/')
            self.assertEqual(friends.data['count'], 1)
            other = friends.data['friends'][0]['friend']['username']
            self.assertEqual(other, 'bob' if who == alice else 'alice')

        # Pending count now zero
        count = self._as(alice).get('/api/social/pending-count/').data
        self.assertEqual(count['friend_requests'], 0)

        # Inverse request while accepted is rejected
        inv = self._as(bob).post('/api/social/request/send/', {'user_id': alice.pk})
        self.assertEqual(inv.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inverse_pending_auto_accepts(self):
        alice, bob = make_user('alice'), make_user('bob')
        self._as(alice).post('/api/social/request/send/', {'user_id': bob.pk})
        # Bob sends back before accepting → auto-accept, single row
        res = self._as(bob).post('/api/social/request/send/', {'user_id': alice.pk})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'accepted')
        self.assertTrue(Friendship.are_friends(alice, bob))
        self.assertEqual(Friendship.objects.count(), 1)

    def test_decline_then_requeue(self):
        alice, bob = make_user('alice'), make_user('bob')
        self._as(alice).post('/api/social/request/send/', {'user_id': bob.pk})
        pk = self._as(bob).get('/api/social/requests/').data['incoming'][0]['id']
        res = self._as(bob).post(
            f'/api/social/request/{pk}/respond/', {'action': 'decline'}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(Friendship.are_friends(alice, bob))

        # Re-request works and flips the row back to pending
        res = self._as(alice).post('/api/social/request/send/', {'user_id': bob.pk})
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Friendship.objects.count(), 1)

    def test_cancel_outgoing(self):
        alice, bob = make_user('alice'), make_user('bob')
        self._as(alice).post('/api/social/request/send/', {'user_id': bob.pk})
        pk = self._as(alice).get('/api/social/requests/').data['outgoing'][0]['id']
        res = self._as(alice).post(f'/api/social/request/{pk}/cancel/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(Friendship.objects.count(), 0)

    def test_block_and_remove_friend(self):
        alice, bob = make_user('alice'), make_user('bob')
        make_friends(alice, bob)

        # Alice removes bob
        res = self._as(alice).post(
            '/api/social/friends/manage/',
            {'user_id': bob.pk, 'action': 'remove'},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(Friendship.are_friends(alice, bob))

        # Re-friend, then block instead
        self._as(alice).post('/api/social/request/send/', {'user_id': bob.pk})
        pk = self._as(bob).get('/api/social/requests/').data['incoming'][0]['id']
        self._as(bob).post(f'/api/social/request/{pk}/respond/', {'action': 'block'})
        self.assertTrue(Friendship.is_blocked(alice, bob))

        # Blocked users can't send requests
        res = self._as(alice).post('/api/social/request/send/', {'user_id': bob.pk})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Search excludes the blocked user
        res = self._as(alice).get('/api/social/users/search/?q=bob')
        self.assertEqual(res.data['results'], [])

    def test_search_exclusions(self):
        alice, bob, carol = make_user('alice'), make_user('bob'), make_user('carol')
        # alice + bob become friends; carol is searchable
        make_friends(alice, bob)
        res = self._as(alice).get('/api/social/users/search/?q=')
        self.assertEqual(res.data['results'], [])
        res = self._as(alice).get('/api/social/users/search/?q=c')
        self.assertEqual([r['username'] for r in res.data['results']], ['carol'])
        res = self._as(alice).get('/api/social/users/search/?q=rol')
        self.assertEqual([r['username'] for r in res.data['results']], ['carol'])
        # q matching only the (excluded) friend bob → nobody
        res = self._as(alice).get('/api/social/users/search/?q=bo')
        self.assertEqual(res.data['results'], [])
        # Self never shows up
        res = self._as(alice).get('/api/social/users/search/?q=ali')
        self.assertEqual(res.data['results'], [])


class ChallengeApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _as(self, user):
        self.client.force_authenticate(user=user)
        return self.client

    def _completed_session(self, user, doc, answers=((0, True, 10.0), (1, False, 8.0), (2, True, 12.0))):
        session = TestSession.objects.create(
            user=user, document=doc, start_elo=1200.0, is_completed=True
        )
        questions = list(doc.questions.all())
        for i, (sel, correct, secs) in enumerate(answers):
            SessionResponse.objects.create(
                session=session, question=questions[i],
                selected_index=sel, is_correct=correct,
                time_taken_sec=secs,
            )
        return session

    def _setup(self):
        alice, bob = make_user('alice'), make_user('bob')
        make_friends(alice, bob)
        doc = Document.objects.create(
            user=alice, filename='physics.pdf', raw_text='Some text'
        )
        for i in range(3):
            Question.objects.create(
                document=doc, question_text=f'Q{i}',
                options=['A', 'B', 'C', 'D'], correct_index=0,
            )
        return alice, bob, doc

    def test_create_requires_friend_and_completed_session(self):
        alice, bob, doc = self._setup()
        stranger = make_user('stranger')

        session = TestSession.objects.create(user=alice, document=doc)
        res = self._as(alice).post('/api/challenges/create/', {
            'session_id': str(session.id),
            'challenged_user_id': bob.pk,
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)  # not completed

        session2 = self._completed_session(alice, doc)
        # stranger is not a friend
        res = self._as(alice).post('/api/challenges/create/', {
            'session_id': str(session2.id),
            'challenged_user_id': stranger.pk,
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_full_duel_flow(self):
        alice, bob, doc = self._setup()
        # alice answered Q0 correct(10s), Q1 wrong(8s), Q2 correct(12s) → 2/3
        session = self._completed_session(
            alice, doc, ((0, True, 10.0), (1, False, 8.0), (2, True, 12.0))
        )
        res = self._as(alice).post('/api/challenges/create/', {
            'session_id': str(session.id),
            'challenged_user_id': bob.pk,
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['challenger_score'], 2)
        pk = res.data['id']

        # Duplicate pending challenge blocked by DB partial unique
        dup = self._as(alice).post('/api/challenges/create/', {
            'session_id': str(session.id),
            'challenged_user_id': bob.pk,
        })
        self.assertEqual(dup.status_code, status.HTTP_400_BAD_REQUEST)

        # Bob fetches questions (answers hidden)
        questions = self._as(bob).get(f'/api/challenges/{pk}/questions/')
        self.assertEqual(questions.status_code, status.HTTP_200_OK)
        self.assertEqual(questions.data['total_questions'], 3)
        for q in questions.data['questions']:
            self.assertNotIn('correct_index', q)

        # Bob answers all 3 correctly in 5s each → wins 3-2
        answers = [
            {'question_id': q['id'], 'selected_index': 0, 'time_taken_sec': 5.0}
            for q in questions.data['questions']
        ]
        submit = self._as(bob).post(
            f'/api/challenges/{pk}/submit/', {'answers': answers}, format='json'
        )
        self.assertEqual(submit.status_code, status.HTTP_200_OK)
        self.assertEqual(submit.data['verdict'], 'won')
        self.assertEqual(submit.data['challenged_score'], 3)
        self.assertEqual(submit.data['winner_username'], 'bob')

        challenge = QuizChallenge.objects.get(pk=pk)
        self.assertEqual(challenge.status, QuizChallenge.Status.COMPLETED)
        self.assertEqual(challenge.winner, bob)

        # Both participants see the completed duel
        out = self._as(alice).get('/api/challenges/').data
        self.assertEqual(len(out['outgoing']), 1)
        self.assertEqual(out['outgoing'][0]['status'], 'completed')
        inc = self._as(bob).get('/api/challenges/').data
        self.assertEqual(len(inc['incoming']), 1)
        self.assertEqual(inc['incoming'][0]['winner_username'], 'bob')

        # Can't play twice
        again = self._as(bob).get(f'/api/challenges/{pk}/questions/')
        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)

    def test_partial_answer_rejected(self):
        alice, bob, doc = self._setup()
        session = self._completed_session(alice, doc)
        res = self._as(alice).post('/api/challenges/create/', {
            'session_id': str(session.id),
            'challenged_user_id': bob.pk,
        })
        pk = res.data['id']
        questions = self._as(bob).get(f'/api/challenges/{pk}/questions/').data['questions']
        partial = [{'question_id': questions[0]['id'], 'selected_index': 0, 'time_taken_sec': 5.0}]
        submit = self._as(bob).post(
            f'/api/challenges/{pk}/submit/', {'answers': partial}, format='json'
        )
        self.assertEqual(submit.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duel_from_legacy_pdf_session(self):
        """Regression: the PDF workspace runs on legacy (pages) sessions with
        integer ids — duels must accept those and grade from the snapshot."""
        from pages.models import (
            UploadedPDF as LegacyPDF,
            Question as LegacyQuestion,
            TestSession as LegacySession,
            SessionResponse as LegacyResponse,
        )
        alice, bob = make_user('alice'), make_user('bob')
        make_friends(alice, bob)
        pdf = LegacyPDF.objects.create(file='uploads/x.pdf', raw_text='t')
        qs = [
            LegacyQuestion.objects.create(
                document=pdf, question_text=f'LQ{i}',
                options=['A', 'B', 'C', 'D'], correct_index=0,
            )
            for i in range(2)
        ]
        session = LegacySession.objects.create(
            user=alice, document=pdf, is_completed=True
        )
        LegacyResponse.objects.create(
            session=session, question=qs[0], selected_index=0,
            is_correct=True, time_taken_sec=7.0,
        )
        LegacyResponse.objects.create(
            session=session, question=qs[1], selected_index=1,
            is_correct=False, time_taken_sec=9.0,
        )

        # Integer session id must be accepted by the create endpoint
        res = self._as(alice).post('/api/challenges/create/', {
            'session_id': str(session.id),  # an int id from the legacy stack
            'challenged_user_id': bob.pk,
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(res.data['challenger_score'], 1)
        self.assertEqual(res.data['question_count'], 2)
        pk = res.data['id']

        # Bob plays against the snapshot and wins
        qs_data = self._as(bob).get(f'/api/challenges/{pk}/questions/')
        self.assertEqual(qs_data.status_code, status.HTTP_200_OK)
        answers = [
            {'question_id': q['id'], 'selected_index': 0, 'time_taken_sec': 3.0}
            for q in qs_data.data['questions']
        ]
        submit = self._as(bob).post(
            f'/api/challenges/{pk}/submit/', {'answers': answers}, format='json'
        )
        self.assertEqual(submit.status_code, status.HTTP_200_OK)
        self.assertEqual(submit.data['verdict'], 'won')
        self.assertEqual(submit.data['challenged_score'], 2)

    def test_expired_duel(self):
        alice, bob, doc = self._setup()
        session = self._completed_session(alice, doc)
        res = self._as(alice).post('/api/challenges/create/', {
            'session_id': str(session.id),
            'challenged_user_id': bob.pk,
        })
        pk = res.data['id']
        QuizChallenge.objects.filter(pk=pk).update(
            expires_at=timezone.now() - timedelta(minutes=5)
        )
        # Listing flips stale pending → expired lazily
        out = self._as(bob).get('/api/challenges/').data
        self.assertEqual(out['incoming'][0]['status'], 'expired')
        play = self._as(bob).get(f'/api/challenges/{pk}/questions/')
        self.assertEqual(play.status_code, status.HTTP_400_BAD_REQUEST)


class FriendLeaderboardTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _as(self, user):
        self.client.force_authenticate(user=user)
        return self.client

    def test_friends_leaderboard_scoped_and_ranked(self):
        alice, bob, carol = make_user('alice'), make_user('bob'), make_user('carol')
        make_friends(alice, bob)
        make_friends(bob, carol)  # carol is bob's friend but NOT alice's

        d1 = DailyQuiz.objects.create(date='2026-09-01')
        DailyQuizSession.objects.create(user=alice, quiz=d1, score=8, total_time_sec=100)
        DailyQuizSession.objects.create(user=bob, quiz=d1, score=6, total_time_sec=120)
        DailyQuizSession.objects.create(user=carol, quiz=d1, score=9, total_time_sec=90)

        # alice's network = alice + bob (carol excluded)
        res = self._as(alice).get('/api/leaderboard/friends/?metric=all_time')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        names = [e['username'] for e in res.data['leaderboard']]
        self.assertEqual(names, ['alice', 'bob'])
        self.assertEqual(res.data['meta']['total_users'], 2)
        self.assertEqual(res.data['meta']['my_rank'], 1)

        # bob's network includes carol → carol ranks 1st
        res = self._as(bob).get('/api/leaderboard/friends/?metric=all_time')
        names = [e['username'] for e in res.data['leaderboard']]
        self.assertEqual(names, ['carol', 'alice', 'bob'])
        self.assertEqual(res.data['meta']['my_rank'], 3)

    def test_streak_and_elo_metrics(self):
        alice, bob = make_user('alice'), make_user('bob')
        make_friends(alice, bob)
        alice.study_profile.current_streak = 7
        alice.study_profile.elo_rating = 1500
        alice.study_profile.save()
        bob.study_profile.current_streak = 3
        bob.study_profile.elo_rating = 1300
        bob.study_profile.save()

        res = self._as(alice).get('/api/leaderboard/friends/?metric=streak')
        self.assertEqual(res.data['leaderboard'][0]['username'], 'alice')
        res = self._as(alice).get('/api/leaderboard/friends/?metric=elo')
        self.assertEqual(res.data['leaderboard'][0]['username'], 'alice')

        bad = self._as(alice).get('/api/leaderboard/friends/?metric=bogus')
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
