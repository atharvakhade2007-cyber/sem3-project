from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from rest_framework import status
from rest_framework.test import APIClient
from django.test import SimpleTestCase, TestCase

from .services.rating_engine import (
    expected_score,
    k_factor,
    resolve_duel_outcome,
    duels_played,
)
from .services import irt_engine as irt

from .models import (
    Friendship, QuizChallenge, Document, Question,
    TestSession, SessionResponse, DailyQuiz, DailyQuestion,
    DailyQuizSession, DailyQuizAnswer,
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
            user=user, document=doc, start_elo=0.0, is_completed=True
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
                explanation=f'Explanation for Q{i}',
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

        # The submit payload carries the detailed per-question review for the
        # challenged user (correct answers + snapshotted explanations).
        review = submit.data['review']
        self.assertEqual(len(review), 3)
        for item in review:
            self.assertEqual(item['is_correct'], True)
            self.assertEqual(item['correct_index'], 0)
            self.assertEqual(item['selected_index'], 0)
            # Explanation matches the question it belongs to
            self.assertEqual(
                item['explanation'], f'Explanation for {item["question_text"]}'
            )

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


class DailyQuizAnswerFlowTests(TestCase):
    """Per-question locked answers (instant feedback without a gameable score)."""

    def setUp(self):
        self.client = APIClient()
        self.user = make_user('quizzy')
        self.client.force_authenticate(user=self.user)
        self.today = timezone.localdate()
        self.quiz = DailyQuiz.objects.create(date=self.today)

        # 2 universal CA + 2 GK on the easy tier (the θ-derived default at
        # 0 Elo) → 4 served questions
        self.ca1 = DailyQuestion.objects.create(
            quiz=self.quiz, category='current_affairs', difficulty_tier=None,
            question_text='CA1', options=['A', 'B', 'C', 'D'],
            correct_index=0, order=1,
        )
        self.ca2 = DailyQuestion.objects.create(
            quiz=self.quiz, category='current_affairs', difficulty_tier=None,
            question_text='CA2', options=['A', 'B', 'C', 'D'],
            correct_index=1, order=2,
        )
        self.gk1 = DailyQuestion.objects.create(
            quiz=self.quiz, category='gk', difficulty_tier='easy',
            question_text='GK1', options=['A', 'B', 'C', 'D'],
            correct_index=2, order=3,
        )
        self.gk2 = DailyQuestion.objects.create(
            quiz=self.quiz, category='gk', difficulty_tier='easy',
            question_text='GK2', options=['A', 'B', 'C', 'D'],
            correct_index=3, order=4,
        )

    def _check(self, q, index):
        return self.client.post(
            '/api/v2/daily-quiz/check/',
            {'question_id': str(q.id), 'selected_index': index},
            format='json',
        )

    def test_check_locks_answer_and_reveals_outcome(self):
        # Wrong answer → outcome revealed, but the row is locked server-side
        res = self._check(self.ca1, 1)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertFalse(res.data['is_correct'])
        self.assertEqual(res.data['correct_index'], 0)
        self.assertIn('explanation', res.data)

        # Replaying the same selection is idempotent
        again = self._check(self.ca1, 1)
        self.assertEqual(again.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DailyQuizAnswer.objects.count(), 1)

        # Changing an answered question is rejected
        flip = self._check(self.ca1, 0)
        self.assertEqual(flip.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(DailyQuizAnswer.objects.count(), 1)

        # today GET exposes the locked answers for resume
        today = self.client.get('/api/v2/daily-quiz/today/')
        self.assertEqual(today.status_code, status.HTTP_200_OK)
        self.assertFalse(today.data['user_completed'])
        self.assertEqual(len(today.data['checked_answers']), 1)
        self.assertEqual(
            today.data['checked_answers'][0]['question_id'], str(self.ca1.id)
        )

    def test_submit_grades_exclusively_from_recorded_answers(self):
        self._check(self.ca1, 1)   # wrong
        self._check(self.gk1, 2)   # correct (GK)

        # A payload claiming every question is correct has no authority —
        # grading uses only the locked answers.
        cheat_payload = [
            {'question_id': str(q.id), 'selected_index': q.correct_index}
            for q in (self.ca1, self.ca2, self.gk1, self.gk2)
        ]
        res = self.client.post(
            '/api/v2/daily-quiz/submit/',
            {'answers': cheat_payload, 'total_time_sec': 42},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['score'], 1)          # only the locked correct one
        self.assertEqual(res.data['gk_correct'], 1)
        self.assertEqual(len(res.data['review']), 2)    # only answered questions

        session = DailyQuizSession.objects.get(user=self.user, quiz=self.quiz)
        self.assertEqual(session.score, 1)

        # Double submit still rejected
        dup = self.client.post(
            '/api/v2/daily-quiz/submit/',
            {'answers': cheat_payload, 'total_time_sec': 1},
            format='json',
        )
        self.assertEqual(dup.status_code, status.HTTP_400_BAD_REQUEST)

    def test_check_rejected_after_completion_and_for_foreign_question(self):
        self._check(self.ca1, 0)
        payload = [
            {'question_id': str(q.id), 'selected_index': q.correct_index}
            for q in (self.ca1, self.ca2, self.gk1, self.gk2)
        ]
        sub = self.client.post(
            '/api/v2/daily-quiz/submit/',
            {'answers': payload, 'total_time_sec': 10},
            format='json',
        )
        self.assertEqual(sub.status_code, status.HTTP_201_CREATED)
        # Once the day's quiz is completed, no more answers can be locked
        res = self._check(self.ca2, 1)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class IrtEngineMathTests(SimpleTestCase):
    """Pure-math checks for the 1PL IRT engine (no DB)."""

    def test_elo_theta_roundtrip(self):
        # 0-based scale: new users start at 0 Elo → neutral θ = 0
        self.assertAlmostEqual(irt.ability_from_elo(0.0), 0.0, places=9)
        self.assertAlmostEqual(irt.elo_from_ability(0.0), 0.0, places=6)
        theta = 1.234
        self.assertAlmostEqual(
            irt.ability_from_elo(irt.elo_from_ability(theta)), theta, places=9
        )

    def test_p_correct_symmetry_and_monotonicity(self):
        self.assertAlmostEqual(irt.p_correct(0.0, 0.0), 0.5, places=9)
        # A 1-point difficulty gap mirrors the probability about 0.5
        self.assertAlmostEqual(
            irt.p_correct(0.0, 1.0),
            1.0 - irt.p_correct(0.0, -1.0),
            places=9,
        )
        # Monotonic in ability
        self.assertGreater(irt.p_correct(1.0, 0.0), irt.p_correct(-1.0, 0.0))

    def test_elo_consistency_with_rating_engine(self):
        """θ mapping makes P(correct | θ, medium) == Elo expected score vs 0."""
        for elo in (-100, 0, 150, 400, 800):
            self.assertAlmostEqual(
                irt.p_correct(irt.ability_from_elo(elo), 0.0),
                expected_score(elo, 0),
                places=9,
            )

    def test_difficulty_calibration(self):
        self.assertEqual(irt.difficulty_from_tier('easy'), -1.0)
        self.assertEqual(irt.difficulty_from_tier('medium'), 0.0)
        self.assertEqual(irt.difficulty_from_tier('hard'), 1.0)
        self.assertEqual(irt.tier_from_difficulty(-0.9), 'easy')
        self.assertEqual(irt.tier_from_difficulty(0.9), 'hard')

    def test_tier_selection_targets_70_percent(self):
        # 0 Elo → θ=0 → easy (P≈0.73) sits closest to the 0.70 target
        self.assertEqual(irt.select_tier_for_ability(irt.ability_from_elo(0)), 'easy')
        # Medium flow state ≈ 150 Elo, hard ≈ 330 Elo on the 0-based scale
        self.assertEqual(irt.select_tier_for_ability(irt.ability_from_elo(150)), 'medium')
        self.assertEqual(irt.select_tier_for_ability(irt.ability_from_elo(330)), 'hard')

    def test_update_theta_direction_and_magnitude(self):
        # Correct / wrong on a 50/50 item: θ ±= LR·0.5
        self.assertAlmostEqual(irt.update_theta(0.0, 0.0, True), 0.15 * 0.5, places=9)
        self.assertAlmostEqual(irt.update_theta(0.0, 0.0, False), -0.15 * 0.5, places=9)
        # A surprising wrong on an easy item moves θ more than an expected correct
        easy = -1.0
        self.assertLess(
            irt.update_theta(0.0, easy, True),
            0.0 - irt.update_theta(0.0, easy, False),
        )

    def test_select_next_question_flow_state(self):
        pool = [
            {'id': 'a', 'difficulty': -1.0},
            {'id': 'b', 'difficulty': 0.0},
            {'id': 'c', 'difficulty': 1.0},
        ]
        # θ=0 → easy (P≈0.73, dist 0.031) beats medium (dist 0.2)
        self.assertEqual(irt.select_next_question(pool, 0.0)['id'], 'a')
        # Elo 330 → hard is the flow-state question
        self.assertEqual(
            irt.select_next_question(pool, irt.ability_from_elo(330))['id'], 'c'
        )
        self.assertIsNone(irt.select_next_question([], 0.0))


class IrtDailyQuizIntegrationTests(TestCase):
    """θ-based tier serving + Elo feedback loop through the daily quiz API."""

    def setUp(self):
        self.client = APIClient()
        self.user = make_user('adaptive')
        self.client.force_authenticate(user=self.user)
        self.today = timezone.localdate()
        self.quiz = DailyQuiz.objects.create(date=self.today)

        # 1 universal CA + 1 GK per tier so any θ-chosen tier is servable
        self.ca = DailyQuestion.objects.create(
            quiz=self.quiz, category='current_affairs', difficulty_tier=None,
            question_text='CA', options=['A', 'B', 'C', 'D'],
            correct_index=0, order=1,
        )
        self.gk = {}
        for order, tier in enumerate(('easy', 'medium', 'hard'), start=2):
            self.gk[tier] = DailyQuestion.objects.create(
                quiz=self.quiz, category='gk', difficulty_tier=tier,
                question_text=f'GK-{tier}', options=['A', 'B', 'C', 'D'],
                correct_index=0, order=order,
            )

    def _today(self):
        return self.client.get('/api/v2/daily-quiz/today/')

    def test_served_tier_tracks_elo(self):
        # 0 Elo (new user default) → easy tier served, medium/hard excluded
        res = self._today()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['gk_skill_tier'], 'easy')
        served_ids = {q['id'] for q in res.data['questions']}
        self.assertIn(str(self.ca.id), served_ids)
        self.assertIn(str(self.gk['easy'].id), served_ids)
        self.assertNotIn(str(self.gk['medium'].id), served_ids)
        self.assertNotIn(str(self.gk['hard'].id), served_ids)

        # Elo 150 → medium
        self.user.study_profile.elo_rating = 150
        self.user.study_profile.save()
        res = self._today()
        self.assertEqual(res.data['gk_skill_tier'], 'medium')
        served_ids = {q['id'] for q in res.data['questions']}
        self.assertIn(str(self.gk['medium'].id), served_ids)

        # Elo 330 → hard, and the profile field is synced to θ
        self.user.study_profile.elo_rating = 330
        self.user.study_profile.save()
        res = self._today()
        self.assertEqual(res.data['gk_skill_tier'], 'hard')
        self.user.study_profile.refresh_from_db()
        self.assertEqual(self.user.study_profile.gk_skill_tier, 'hard')

    def test_completion_nudges_elo_from_gk_performance(self):
        self._today()  # sync tier (easy) and serve questions
        gk = self.gk['easy']
        check = self.client.post(
            '/api/v2/daily-quiz/check/',
            {'question_id': str(gk.id), 'selected_index': 0},  # correct
            format='json',
        )
        self.assertEqual(check.status_code, status.HTTP_201_CREATED)
        # Payload is ignored — grading uses the locked rows (new flow)
        res = self.client.post(
            '/api/v2/daily-quiz/submit/',
            {'answers': [{'question_id': str(gk.id), 'selected_index': 0}],
             'total_time_sec': 30},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['gk_correct'], 1)
        # 1 correct on easy (P≈0.731): θ += 0.15·(1−0.731) ≈ +7.0 Elo
        self.user.study_profile.refresh_from_db()
        self.assertAlmostEqual(
            self.user.study_profile.elo_rating, 7.0, delta=0.2
        )
        self.assertEqual(res.data['gk_skill_tier'], 'easy')

    def test_wrong_gk_answer_lowers_elo(self):
        self._today()
        gk = self.gk['easy']
        self.client.post(
            '/api/v2/daily-quiz/check/',
            {'question_id': str(gk.id), 'selected_index': 1},  # wrong
            format='json',
        )
        res = self.client.post(
            '/api/v2/daily-quiz/submit/',
            {'answers': [{'question_id': str(gk.id), 'selected_index': 1}],
             'total_time_sec': 30},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        # 1 wrong on easy (P≈0.731): θ += 0.15·(0−0.731) ≈ −19.1 Elo
        self.user.study_profile.refresh_from_db()
        self.assertAlmostEqual(
            self.user.study_profile.elo_rating, -19.1, delta=0.2
        )

    def test_legacy_submit_path_also_nudges_elo(self):
        """Payload-graded submissions (no /check/ calls) feed Elo too."""
        self._today()
        gk = self.gk['easy']
        res = self.client.post(
            '/api/v2/daily-quiz/submit/',
            {'answers': [{'question_id': str(gk.id), 'selected_index': 0}],
             'total_time_sec': 20},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.user.study_profile.refresh_from_db()
        self.assertAlmostEqual(
            self.user.study_profile.elo_rating, 7.0, delta=0.2
        )


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
        alice.study_profile.elo_rating = 300
        alice.study_profile.save()
        bob.study_profile.current_streak = 3
        bob.study_profile.elo_rating = 100
        bob.study_profile.save()

        res = self._as(alice).get('/api/leaderboard/friends/?metric=streak')
        self.assertEqual(res.data['leaderboard'][0]['username'], 'alice')
        res = self._as(alice).get('/api/leaderboard/friends/?metric=elo')
        self.assertEqual(res.data['leaderboard'][0]['username'], 'alice')

        bad = self._as(alice).get('/api/leaderboard/friends/?metric=bogus')
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)


class RatingEngineMathTests(SimpleTestCase):
    """Pure-math checks for the Elo engine (no DB)."""

    def test_expected_score(self):
        self.assertAlmostEqual(expected_score(0, 0), 0.5, places=6)
        # A 400-point favourite ≈ 91% win probability
        self.assertAlmostEqual(expected_score(400, 0), 0.9090909, places=6)
        self.assertAlmostEqual(expected_score(0, 400), 0.0909091, places=6)

    def test_k_factor_bands(self):
        # Provisional: fewer than 20 duels, regardless of rating
        self.assertEqual(k_factor(0, 0), 40)
        self.assertEqual(k_factor(19, 900), 40)
        # Standard established player
        self.assertEqual(k_factor(20, 0), 20)
        self.assertEqual(k_factor(20, 800), 20)
        # High tier: 20+ duels AND rating above 800 (0-based scale)
        self.assertEqual(k_factor(20, 800.1), 10)
        self.assertEqual(k_factor(99, 1300), 10)

    def test_resolve_duel_outcome(self):
        # Higher score always wins
        self.assertEqual(
            resolve_duel_outcome(3, 50, 2, 40), ('challenger', 1.0)
        )
        self.assertEqual(
            resolve_duel_outcome(1, 5, 3, 99), ('challenged', 0.0)
        )
        # Equal scores → faster time wins when the gap is >= 1s
        self.assertEqual(
            resolve_duel_outcome(2, 50.0, 2, 49.0), ('challenged', 0.0)
        )
        self.assertEqual(
            resolve_duel_outcome(2, 45.0, 2, 46.0), ('challenger', 1.0)
        )
        # Equal scores within 1s → draw
        self.assertEqual(
            resolve_duel_outcome(2, 50.0, 2, 50.4), ('draw', 0.5)
        )
        self.assertEqual(
            resolve_duel_outcome(2, 60.0, 2, 60.0), ('draw', 0.5)
        )


class DuelEloIntegrationTests(TestCase):
    """Completing a duel applies Elo to both users' study_core profiles."""

    def setUp(self):
        self.client = APIClient()

    def _as(self, user):
        self.client.force_authenticate(user=user)
        return self.client

    def _completed_session(self, user, doc, answers):
        session = TestSession.objects.create(
            user=user, document=doc, start_elo=0.0, is_completed=True
        )
        questions = list(doc.questions.all())
        for i, (sel, correct, secs) in enumerate(answers):
            SessionResponse.objects.create(
                session=session, question=questions[i],
                selected_index=sel, is_correct=correct, time_taken_sec=secs,
            )
        return session

    def _setup(self):
        alice = make_user('alice')
        bob = make_user('bob')
        make_friends(alice, bob)
        doc = Document.objects.create(user=alice, filename='quiz.pdf', raw_text='x')
        for i in range(3):
            Question.objects.create(
                document=doc, question_text=f'Q{i}',
                options=['A', 'B', 'C', 'D'], correct_index=0,
            )
        return alice, bob, doc

    def _create_duel(self, challenger, challenged, doc, answers):
        session = self._completed_session(challenger, doc, answers)
        res = self._as(challenger).post('/api/challenges/create/', {
            'session_id': str(session.id),
            'challenged_user_id': challenged.pk,
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        return res.data['id']

    def _questions_for(self, user, pk):
        data = self._as(user).get(f'/api/challenges/{pk}/questions/').data
        return data['questions']

    def test_win_updates_both_profiles(self):
        alice, bob, doc = self._setup()
        alice.study_profile.elo_rating = 100
        bob.study_profile.elo_rating = 200
        alice.study_profile.save(); bob.study_profile.save()

        # Alice (challenger) scores 2/3 in 40s
        pk = self._create_duel(
            alice, bob, doc,
            ((0, True, 10.0), (0, True, 10.0), (1, False, 20.0)),
        )
        # Bob answers every question, 3/3 in 15s → wins
        qs = self._questions_for(bob, pk)
        res = self._as(bob).post(f'/api/challenges/{pk}/submit/', {
            'answers': [
                {'question_id': q['id'], 'selected_index': 0, 'time_taken_sec': 5.0}
                for q in qs
            ],
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['verdict'], 'won')

        # Expected: E(200 vs 100) ≈ 0.6401, provisional K=40 → +14.4 / −14.4
        alice.refresh_from_db(); bob.refresh_from_db()
        self.assertAlmostEqual(bob.study_profile.elo_rating, 214.4, delta=0.2)
        self.assertAlmostEqual(alice.study_profile.elo_rating, 85.6, delta=0.2)
        self.assertAlmostEqual(res.data['elo_change'], 14.4, delta=0.2)
        self.assertAlmostEqual(
            res.data['challenger_elo_change'], -14.4, delta=0.2
        )
        # Both now have one duel played
        self.assertEqual(duels_played(alice), 1)
        self.assertEqual(duels_played(bob), 1)

    def test_draw_within_one_second(self):
        alice, bob, doc = self._setup()
        alice.study_profile.elo_rating = 300
        bob.study_profile.elo_rating = 0
        alice.study_profile.save(); bob.study_profile.save()

        # Alice 2/3 in exactly 60.0s
        pk = self._create_duel(
            alice, bob, doc,
            ((0, True, 20.0), (0, True, 20.0), (1, False, 20.0)),
        )
        # Bob ties 2/3 but finishes in 60.4s → within 1s → draw
        qs = self._questions_for(bob, pk)
        answers = [
            {'question_id': qs[0]['id'], 'selected_index': 0, 'time_taken_sec': 20.1},
            {'question_id': qs[1]['id'], 'selected_index': 1, 'time_taken_sec': 20.1},
            {'question_id': qs[2]['id'], 'selected_index': 0, 'time_taken_sec': 20.2},
        ]
        res = self._as(bob).post(f'/api/challenges/{pk}/submit/', {
            'answers': answers,
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['verdict'], 'draw')
        self.assertIsNone(res.data['winner_username'])
        challenge = QuizChallenge.objects.get(pk=pk)
        self.assertIsNone(challenge.winner)

        # E(300 vs 0) ≈ 0.849, draw S=0.5 → favourite sheds ~14, underdog gains ~14
        alice.refresh_from_db(); bob.refresh_from_db()
        self.assertAlmostEqual(alice.study_profile.elo_rating, 286.0, delta=0.2)
        self.assertAlmostEqual(bob.study_profile.elo_rating, 14.0, delta=0.2)

    def test_time_gap_over_one_second_not_a_draw(self):
        alice, bob, doc = self._setup()
        # Alice 2/3 in 60.0s
        pk = self._create_duel(
            alice, bob, doc,
            ((0, True, 20.0), (0, True, 20.0), (1, False, 20.0)),
        )
        # Bob ties 2/3 in 55s (gap 5s ≥ 1s) → Bob wins the tie-break
        qs = self._questions_for(bob, pk)
        answers = [
            {'question_id': qs[0]['id'], 'selected_index': 0, 'time_taken_sec': 19.0},
            {'question_id': qs[1]['id'], 'selected_index': 1, 'time_taken_sec': 18.0},
            {'question_id': qs[2]['id'], 'selected_index': 0, 'time_taken_sec': 18.0},
        ]
        res = self._as(bob).post(f'/api/challenges/{pk}/submit/', {
            'answers': answers,
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['verdict'], 'won')
        self.assertEqual(res.data['winner_username'], 'bob')
        self.assertGreater(res.data['elo_change'], 0)

    def test_k_factor_uses_duel_history(self):
        alice, bob, doc = self._setup()
        carol = make_user('carol')

        # Alice already has 19 completed duels; this one makes 20 → K drops to 20.
        for _ in range(19):
            QuizChallenge.objects.create(
                challenger=alice, challenged_user=carol,
                status=QuizChallenge.Status.COMPLETED,
                challenger_score=0, challenged_score=0,
                expires_at=timezone.now() + timedelta(hours=1),
            )
        self.assertEqual(duels_played(alice), 19)
        self.assertEqual(duels_played(bob), 0)

        pk = self._create_duel(
            alice, bob, doc,
            ((0, True, 20.0), (0, True, 20.0), (1, False, 20.0)),
        )
        qs = self._questions_for(bob, pk)
        res = self._as(bob).post(f'/api/challenges/{pk}/submit/', {
            'answers': [
                {'question_id': q['id'], 'selected_index': 0, 'time_taken_sec': 5.0}
                for q in qs
            ],
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Both at 0 → E=0.5. Alice (K=20) loses 10, Bob (K=40, provisional) wins 20.
        alice.refresh_from_db(); bob.refresh_from_db()
        self.assertAlmostEqual(alice.study_profile.elo_rating, -10.0, delta=0.2)
        self.assertAlmostEqual(bob.study_profile.elo_rating, 20.0, delta=0.2)
        self.assertEqual(duels_played(alice), 20)
        self.assertEqual(duels_played(bob), 1)
