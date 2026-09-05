import io

p = 'pages/views.py'

with open(p, 'rb') as f:
    data = f.read()
text = data.decode('utf-8')

# --- api_test_start: insert question_count handling ---

old_start = """@csrf_exempt
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_test_start(request):
    \"\"\"REST API: Create TestSession and select first question.\"\"\"
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
            if not text.strip():
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
"""

new_start = """@csrf_exempt
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_test_start(request):
    \"\"\"REST API: Create TestSession and select first question.

    Supports user-defined quiz length: if ``question_count`` (N) is provided,
    the backend generates exactly 2*N questions, evenly split across
    Easy/Medium/Hard, stores them as the pool, and adaptively serves exactly N.
    The unused N questions remain in the DB but are never served and are NOT
    counted as questions_attempted.

    If ``question_count`` is omitted, the legacy behaviour (serve the
    full generated or existing set) is used.
    \"\"\"
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    data = _extract_data_from_request(request)
    doc_id = data.get('document_id')

    if not doc_id:
        return JsonResponse({'error': 'document_id required'}, status=400)

    user, profile = _resolve_user_and_profile(request, data)
    pdf = get_object_or_404(UploadedPDF, id=doc_id)

    requested_n = data.get('question_count', None)
    if requested_n is not None:
        try:
            requested_n = int(requested_n)
        except (TypeError, ValueError):
            requested_n = None

    # If the user requested a specific N, generate exactly 2N questions.
    if requested_n is not None:
        generated_n = 2 * requested_n
        try:
            extracted_text = pdf.raw_text or extract_text_from_pdf(pdf.file.path)
            if not extracted_text.strip():
                raise ValueError("Document has no extractable text")
            questions_data = generate_question_bank(
                text=extracted_text,
                num_questions=generated_n,
                api_key=data.get('api_key'),
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
        except Exception as e:
            return JsonResponse({'error': f'Failed to generate questions: {str(e)}'}, status=500)

    questions = Question.objects.filter(document=pdf)

    # Create session with the user-defined-length metadata.
    session = TestSession.objects.create(
        user=user,
        document=pdf,
        start_elo=profile.elo_rating,
        requested_questions=requested_n,
        questions_generated_count=questions.count(),
    )

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
        'requested_questions': requested_n,
        'questions_to_answer': requested_n if requested_n is not None else questions.count(),
        'questions_generated': questions.count(),
        'question': {
            'id': question.id,
            'question_text': question.question_text,
            'options': question.options,
            'difficulty_label': question.difficulty_label,
            'difficulty_rating': question.difficulty_rating,
        },
        'total_questions_available': questions.count(),
    }, status=201)
"""

assert old_start in text, "old_start block not found verbatim"
text = text.replace(old_start, new_start)

# --- api_test_submit_answer: count answers, end session after N ---

old_submit_end = """    # Get next question
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
"""

new_submit_end = """    # Track how many questions this session has actually answered.
    session.questions_answered_count = session.responses.count()
    session.save(update_fields=['questions_answered_count'])

    # Get next question from the remaining pool.
    answered_ids = session.responses.values_list('question_id', flat=True)
    available = Question.objects.filter(
        document=session.document
    ).exclude(id__in=answered_ids).values('id', 'difficulty_rating')

    available_list = list(available)
    next_question = select_next_question(new_user_elo, available_list)

    questions_to_answer = (
        session.requested_questions
        if session.requested_questions is not None
        else Question.objects.filter(document=session.document).count()
    )

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
        'questions_answered': session.questions_answered_count,
        'questions_to_answer': questions_to_answer,
        'questions_generated': session.questions_generated_count,
        'total_available': Question.objects.filter(document=session.document).count(),
    }

    # End the session once the user has answered the requested N questions.
    # Legacy (no requested N) still ends when the pool is exhausted.
    if (
        session.requested_questions is not None
        and session.questions_answered_count >= session.requested_questions
    ):
        session.is_completed = True
        session.end_elo = new_user_elo
        session.save()
        response_data['session_completed'] = True
    elif next_question:
        q = Question.objects.get(id=next_question['id'])
        response_data['next_question'] = {
            'id': q.id,
            'question_text': q.question_text,
            'options': q.options,
            'difficulty_label': q.difficulty_label,
            'difficulty_rating': q.difficulty_rating,
        }
    else:
        session.is_completed = True
        session.end_elo = new_user_elo
        session.save()
        response_data['session_completed'] = True
        response_data['error'] = 'Question pool exhausted before completing the requested quiz.'

    return JsonResponse(response_data, status=200)
"""

assert old_submit_end in text, "old_submit_end block not found verbatim"
text = text.replace(old_submit_end, new_submit_end)

with open(p, 'wb') as f:
    f.write(text.encode('utf-8'))

print("pages/views.py updated OK")
