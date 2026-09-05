import os
import json
import time
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib.auth.models import User

from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import (
    UploadedPDF, Question, UserProfile, Flashcard, Summary,
    TestSession, SessionResponse,
)
from .forms import PDFUploadForm
from .utils.pdf_parser import extract_text_from_pdf
from .utils.llm_generator import (
    generate_summary,
    generate_flashcards,
    generate_question_bank,
)
from .utils.adaptive_engine import (
    expected_win_probability,
    dynamic_k_factor,
    response_latency_weight,
    calculate_elo_update,
    select_next_question,
    get_difficulty_label,
    get_difficulty_badge,
    DIFFICULTY_SEEDS,
)


# ═══════════════════════════════════════════════
#  Helper: resolve user and profile
# ═══════════════════════════════════════════════

def _resolve_user_and_profile(request, data=None):
    """Resolve the authenticated request user and their profile.

    JWT auth is enforced on all REST API views (see @api_view + IsAuthenticated
    below), so request.user is always an authenticated User here.
    """
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    return request.user, profile


def _extract_data_from_request(request):
    """Extract JSON body or POST data as a dict."""
    data = {}
    if request.body:
        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception:
            data = request.POST.dict()
    else:
        data = request.POST.dict()
    return data


# ═══════════════════════════════════════════════
#  Page Views
# ═══════════════════════════════════════════════

def dashboard_view(request):
    """Main dashboard: upload PDFs and choose actions."""
    recent_pdfs = UploadedPDF.objects.all()[:10]

    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_pdf = form.save()

            try:
                pdf_path = uploaded_pdf.file.path
                extracted_text = extract_text_from_pdf(pdf_path)

                if not extracted_text.strip():
                    raise ValueError("Extracted text from PDF is empty.")

                # Save extracted text to document
                uploaded_pdf.raw_text = extracted_text
                uploaded_pdf.processed = True
                uploaded_pdf.save()

                messages.success(
                    request,
                    f"Successfully uploaded '{uploaded_pdf.file.name}'! "
                    f"Choose what to do with it."
                )
                return redirect('pdf_action', pdf_id=uploaded_pdf.id)

            except Exception as e:
                messages.error(request, f"Error processing PDF: {str(e)}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = PDFUploadForm()

    return render(request, 'pages/dashboard.html', {
        'form': form,
        'recent_pdfs': recent_pdfs,
    })


def pdf_action_view(request, pdf_id):
    """Action selection page: choose Summary, Flashcards, or Adaptive Test."""
    pdf = get_object_or_404(UploadedPDF, id=pdf_id)
    if not pdf.processed:
        messages.warning(request, "This PDF hasn't been fully processed yet.")
        return redirect('dashboard')
    return render(request, 'pages/action_select.html', {'pdf': pdf})


def summary_view(request, pdf_id):
    """Display the generated summary for a PDF. Generates on-demand if missing."""
    pdf = get_object_or_404(UploadedPDF, id=pdf_id)
    summary, created = Summary.objects.get_or_create(document=pdf)

    if created or not summary.executive_summary:
        try:
            extracted_text = pdf.raw_text or extract_text_from_pdf(pdf.file.path)
            if not extracted_text.strip():
                raise ValueError("Extracted text from PDF is empty.")
            api_key = request.GET.get('api_key') or None
            summary_data = generate_summary(text=extracted_text, api_key=api_key)
            summary.executive_summary = summary_data.get('executive_summary', '')
            summary.key_concepts = summary_data.get('key_concepts', [])
            summary.terminology = summary_data.get('terminology', [])
            summary.save()
        except Exception as e:
            messages.error(request, f"Error generating summary: {str(e)}")

    return render(request, 'pages/summary.html', {'pdf': pdf, 'summary': summary})


def flashcards_view(request, pdf_id):
    """Interactive flashcard viewer. Generates on-demand if missing."""
    pdf = get_object_or_404(UploadedPDF, id=pdf_id)
    cards = pdf.flashcards.all()

    if not cards.exists():
        try:
            extracted_text = pdf.raw_text or extract_text_from_pdf(pdf.file.path)
            if not extracted_text.strip():
                raise ValueError("Extracted text from PDF is empty.")
            api_key = request.GET.get('api_key') or None
            cards_data = generate_flashcards(text=extracted_text, api_key=api_key)
            flashcard_objects = [
                Flashcard(document=pdf, front=c['front'], back=c['back'], order=i)
                for i, c in enumerate(cards_data)
            ]
            Flashcard.objects.bulk_create(flashcard_objects)
            cards = pdf.flashcards.all()
        except Exception as e:
            messages.error(request, f"Error generating flashcards: {str(e)}")

    return render(request, 'pages/flashcards.html', {'pdf': pdf, 'cards': cards})


def adaptive_test_view(request, pdf_id):
    """Adaptive test quiz page."""
    pdf = get_object_or_404(UploadedPDF, id=pdf_id)
    return render(request, 'pages/adaptive_test.html', {'pdf': pdf})


# ═══════════════════════════════════════════════
#  REST API — Document Management
# ═══════════════════════════════════════════════

@csrf_exempt
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_upload_document(request):
    """REST API: Upload PDF, parse text, store document."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file uploaded'}, status=400)

    pdf_file = request.FILES['file']

    try:
        uploaded_pdf = UploadedPDF.objects.create(file=pdf_file)
        extracted_text = extract_text_from_pdf(uploaded_pdf.file.path)

        uploaded_pdf.raw_text = extracted_text
        uploaded_pdf.processed = True
        uploaded_pdf.save()

        return JsonResponse({
            'success': True,
            'document_id': uploaded_pdf.id,
            'filename': uploaded_pdf.file.name,
            'text_length': len(extracted_text),
            'created_at': uploaded_pdf.uploaded_at.isoformat(),
        }, status=201)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_generate_summary(request, doc_id):
    """REST API: Generate and return structured summary for a document."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    pdf = get_object_or_404(UploadedPDF, id=doc_id)
    data = _extract_data_from_request(request)
    api_key = data.get('api_key') or None

    try:
        extracted_text = pdf.raw_text or extract_text_from_pdf(pdf.file.path)
        if not extracted_text.strip():
            raise ValueError("Document has no extractable text")

        summary_data = generate_summary(text=extracted_text, api_key=api_key)

        # Save to DB
        summary, _ = Summary.objects.get_or_create(document=pdf)
        summary.executive_summary = summary_data.get('executive_summary', '')
        summary.key_concepts = summary_data.get('key_concepts', [])
        summary.terminology = summary_data.get('terminology', [])
        summary.save()

        return JsonResponse({
            'success': True,
            'document_id': doc_id,
            'summary': summary_data,
        }, status=200)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_generate_flashcards(request, doc_id):
    """REST API: Generate and return 20 flashcards for a document."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    pdf = get_object_or_404(UploadedPDF, id=doc_id)
    data = _extract_data_from_request(request)
    api_key = data.get('api_key') or None

    try:
        extracted_text = pdf.raw_text or extract_text_from_pdf(pdf.file.path)
        if not extracted_text.strip():
            raise ValueError("Document has no extractable text")

        cards_data = generate_flashcards(text=extracted_text, api_key=api_key)

        # Save to DB
        pdf.flashcards.all().delete()
        flashcard_objects = [
            Flashcard(document=pdf, front=c['front'], back=c['back'], order=i)
            for i, c in enumerate(cards_data)
        ]
        Flashcard.objects.bulk_create(flashcard_objects)

        return JsonResponse({
            'success': True,
            'document_id': doc_id,
            'flashcards': cards_data,
            'count': len(cards_data),
        }, status=200)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ═══════════════════════════════════════════════
#  REST API — Adaptive Test
# ═══════════════════════════════════════════════

@csrf_exempt
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_generate_question_bank(request):
    """REST API: Generate question bank for a document."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    data = _extract_data_from_request(request)
    doc_id = data.get('document_id')
    api_key = data.get('api_key') or None
    num_questions = int(data.get('num_questions', 20))

    if not doc_id:
        return JsonResponse({'error': 'document_id required'}, status=400)

    pdf = get_object_or_404(UploadedPDF, id=doc_id)

    try:
        extracted_text = pdf.raw_text or extract_text_from_pdf(pdf.file.path)
        if not extracted_text.strip():
            raise ValueError("Document has no extractable text")

        questions_data = generate_question_bank(
            text=extracted_text,
            num_questions=num_questions,
            api_key=api_key
        )

        # Save questions to DB
        question_objects = []
        for item in questions_data:
            q = Question(
                document=pdf,
                question_text=item['question'],
                options=item['options'],
                correct_index=item['correct_index'],
                explanation=item.get('explanation', ''),
                difficulty_label=item['difficulty_label'],
                difficulty_rating=item['difficulty_rating'],
            )
            question_objects.append(q)
        Question.objects.bulk_create(question_objects)

        return JsonResponse({
            'success': True,
            'document_id': doc_id,
            'question_count': len(question_objects),
            'questions': [
                {
                    'id': q.id,
                    'question_text': q.question_text,
                    'options': q.options,
                    'difficulty_label': q.difficulty_label,
                    'difficulty_rating': q.difficulty_rating,
                }
                for q in question_objects
            ],
        }, status=201)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_test_start(request):
    """REST API: Create TestSession and select first question."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    data = _extract_data_from_request(request)
    doc_id = data.get('document_id')

    if not doc_id:
        return JsonResponse({'error': 'document_id required'}, status=400)

    user, profile = _resolve_user_and_profile(request, data)
    pdf = get_object_or_404(UploadedPDF, id=doc_id)

    # Auto-generate question bank if none exist
    questions = Question.objects.filter(document=pdf)
    if not questions.exists():
        try:
            extracted_text = pdf.raw_text or extract_text_from_pdf(pdf.file.path)
            if not extracted_text.strip():
                raise ValueError("Document has no extractable text")
            questions_data = generate_question_bank(
                text=extracted_text,
                num_questions=20,
                api_key=data.get('api_key')
            )
            question_objects = [
                Question(
                    document=pdf,
                    question_text=item['question'],
                    options=item['options'],
                    correct_index=item['correct_index'],
                    explanation=item.get('explanation', ''),
                    difficulty_label=item['difficulty_label'],
                    difficulty_rating=item['difficulty_rating'],
                )
                for item in questions_data
            ]
            Question.objects.bulk_create(question_objects)
            questions = Question.objects.filter(document=pdf)
        except Exception as e:
            return JsonResponse({'error': f'Failed to generate questions: {str(e)}'}, status=500)

    # Create session
    session = TestSession.objects.create(
        user=user,
        document=pdf,
        start_elo=profile.elo_rating,
    )

    # Get all question IDs as dicts
    all_questions = list(questions.values('id', 'difficulty_rating'))

    # Select optimal first question
    selected = select_next_question(profile.elo_rating, all_questions)
    if not selected:
        return JsonResponse({'error': 'Could not select a question'}, status=500)

    question = Question.objects.get(id=selected['id'])

    return JsonResponse({
        'success': True,
        'session_id': session.id,
        'document_id': doc_id,
        'start_elo': profile.elo_rating,
        'question': {
            'id': question.id,
            'question_text': question.question_text,
            'options': question.options,
            'difficulty_label': question.difficulty_label,
            'difficulty_rating': question.difficulty_rating,
        },
        'total_questions_available': questions.count(),
    }, status=201)


@csrf_exempt
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_test_submit_answer(request):
    """REST API: Submit answer, compute Elo shift, return next question."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    data = _extract_data_from_request(request)
    session_id = data.get('session_id')
    question_id = data.get('question_id')
    selected_index = data.get('selected_index')
    time_taken_sec = float(data.get('time_taken_sec', 0))

    if not all([session_id, question_id, selected_index is not None]):
        return JsonResponse({
            'error': 'session_id, question_id, and selected_index required'
        }, status=400)

    user, profile = _resolve_user_and_profile(request, data)
    session = get_object_or_404(TestSession, id=session_id, user=user)

    if session.is_completed:
        return JsonResponse({'error': 'Session already completed'}, status=400)

    question = get_object_or_404(Question, id=question_id)
    is_correct = (int(selected_index) == question.correct_index)

    # Calculate Elo update
    new_user_elo, new_question_elo = calculate_elo_update(
        user_elo=profile.elo_rating,
        question_elo=question.difficulty_rating,
        is_correct=is_correct,
        total_answered=profile.total_questions_answered,
        time_taken_sec=time_taken_sec,
    )

    # Record response
    response = SessionResponse.objects.create(
        session=session,
        question=question,
        selected_index=int(selected_index),
        is_correct=is_correct,
        time_taken_sec=time_taken_sec,
        user_elo_before=profile.elo_rating,
        user_elo_after=new_user_elo,
    )

    # Update question stats
    question.times_served += 1
    if is_correct:
        question.times_correct += 1
    question.difficulty_rating = new_question_elo
    question.save()

    # Update user profile
    profile.elo_rating = new_user_elo
    profile.total_questions_answered += 1
    if is_correct:
        profile.total_correct += 1
        profile.streak += 1
    else:
        profile.streak = 0
    profile.save()

    # Get next question
    answered_ids = session.responses.values_list('question_id', flat=True)
    available = Question.objects.filter(
        document=session.document
    ).exclude(id__in=answered_ids).values('id', 'difficulty_rating')

    available_list = list(available)
    next_question = select_next_question(new_user_elo, available_list)

    response_data = {
        'success': True,
        'is_correct': is_correct,
        'correct_index': question.correct_index,
        'explanation': question.explanation,
        'selected_index': int(selected_index),
        'user_elo_before': profile.elo_rating - (new_user_elo - profile.elo_rating),
        'user_elo_after': new_user_elo,
        'elo_change': new_user_elo - (profile.elo_rating - (new_user_elo - profile.elo_rating)),
        'question_difficulty': question.difficulty_label,
        'questions_answered': session.responses.count(),
        'total_available': Question.objects.filter(document=session.document).count(),
    }

    if next_question:
        q = Question.objects.get(id=next_question['id'])
        response_data['next_question'] = {
            'id': q.id,
            'question_text': q.question_text,
            'options': q.options,
            'difficulty_label': q.difficulty_label,
            'difficulty_rating': q.difficulty_rating,
        }
    else:
        # Auto-complete if no more questions
        session.is_completed = True
        session.end_elo = new_user_elo
        session.save()
        response_data['session_completed'] = True

    return JsonResponse(response_data, status=200)


@csrf_exempt
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_test_complete(request):
    """REST API: Complete session, return comprehensive review data."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    data = _extract_data_from_request(request)
    session_id = data.get('session_id')

    if not session_id:
        return JsonResponse({'error': 'session_id required'}, status=400)

    user, profile = _resolve_user_and_profile(request, data)
    session = get_object_or_404(TestSession, id=session_id, user=user)

    if not session.is_completed:
        session.is_completed = True
        session.end_elo = profile.elo_rating
        session.save()

    # Get all responses
    responses = session.responses.select_related('question').all()

    # Calculate stats
    total = responses.count()
    correct = responses.filter(is_correct=True).count()
    accuracy = (correct / total * 100) if total > 0 else 0

    # Build breakdown
    breakdown = []
    for resp in responses:
        breakdown.append({
            'question_text': resp.question.question_text,
            'options': resp.question.options,
            'correct_index': resp.question.correct_index,
            'selected_index': resp.selected_index,
            'is_correct': resp.is_correct,
            'time_taken_sec': resp.time_taken_sec,
            'difficulty_label': resp.question.difficulty_label,
            'difficulty_rating': resp.question.difficulty_rating,
            'explanation': resp.question.explanation,
            'user_elo_before': resp.user_elo_before,
            'user_elo_after': resp.user_elo_after,
        })

    return JsonResponse({
        'session_id': session.id,
        'start_elo': session.start_elo,
        'end_elo': session.end_elo or profile.elo_rating,
        'accuracy': round(accuracy, 1),
        'correct_count': correct,
        'total_questions': total,
        'final_elo': profile.elo_rating,
        'rating_badge': get_difficulty_badge(profile.elo_rating),
        'breakdown': breakdown,
    }, status=200)
