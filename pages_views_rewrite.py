with open('pages/views.py','rb') as f:
    data = f.read()
text = data.decode('utf-8')

start_idx = text.find('def api_test_start(')
rest = text[start_idx+10:]
nxt = rest.find('\ndef ')
end_idx = start_idx + 10 + nxt
old_block = text[start_idx:end_idx]

new_block = (
'def api_test_start(request):\r\n'
'    """REST API: Create TestSession and select first question.\r\n'
'\r\n'
'    Supports user-defined quiz length: if `question_count` (N) is provided,\r\n'
'    the backend generates exactly 2*N questions, evenly split across\r\n'
'    Easy/Medium/Hard, stores them as the pool, and adaptively serves exactly N.\r\n'
'    The unused N questions remain in the DB but are never served and are NOT\r\n'
'    counted as questions_attempted.\r\n'
'\r\n'
'    If `question_count` is omitted, the legacy behaviour (serve the\r\n'
'    full generated or existing set) is used.\r\n'
'    """\r\n'
"    if request.method != 'POST':\r\n"
"        return JsonResponse({'error': 'POST method required'}, status=405)\r\n"
'\r\n'
'    data = _extract_data_from_request(request)\r\n'
"    doc_id = data.get('document_id')\r\n"
'\r\n'
'    if not doc_id:\r\n'
"        return JsonResponse({'error': 'document_id required'}, status=400)\r\n"
'\r\n'
'    user, profile = _resolve_user_and_profile(request, data)\r\n'
'    pdf = get_object_or_404(UploadedPDF, id=doc_id)\r\n'
'\r\n'
'    requested_n = data.get(\'question_count\', None)\r\n'
'    if requested_n is not None:\r\n'
'        try:\r\n'
'            requested_n = int(requested_n)\r\n'
'        except (TypeError, ValueError):\r\n'
'            requested_n = None\r\n'
'\r\n'
'    # If the user requested a specific N, generate exactly 2N questions.\r\n'
'    if requested_n is not None:\r\n'
'        generated_n = 2 * requested_n\r\n'
'        try:\r\n'
'            extracted_text = pdf.raw_text or extract_text_from_pdf(pdf.file.path)\r\n'
'            if not text.strip():\r\n'
'                raise ValueError("Document has no extractable text")\r\n'
'            questions_data = generate_question_bank(\r\n'
'                text=extracted_text,\r\n'
'                num_questions=generated_n,\r\n'
"                api_key=data.get('api_key'),\r\n"
'            )\r\n'
'            question_objects = [\r\n'
'                Question(\r\n'
'                    document=pdf,\r\n'
'                    question_text=item[\'question\'],\r\n'
'                    options=item[\'options\'],\r\n'
'                    correct_index=item[\'correct_index\'],\r\n'
'                    explanation=item.get(\'explanation\', \'\'),\r\n'
"                    difficulty_label=item['difficulty_label'],\r\n"
"                    difficulty_rating=item['difficulty_rating'],\r\n"
'                )\r\n'
'                for item in questions_data\r\n'
'            ]\r\n'
'            Question.objects.bulk_create(question_objects)\r\n'
'        except Exception as e:\r\n'
"            return JsonResponse({'error': f'Failed to generate questions: {str(e)}'}, status=500)\r\n"
'\r\n'
'    questions = Question.objects.filter(document=pdf)\r\n'
'\r\n'
'    # Create session with the user-defined-length metadata.\r\n'
'    session = TestSession.objects.create(\r\n'
'        user=user,\r\n'
'        document=pdf,\r\n'
'        start_elo=profile.elo_rating,\r\n'
'        requested_questions=requested_n,\r\n'
'        questions_generated_count=questions.count(),\r\n'
'    )\r\n'
'\r\n'
'    all_questions = list(questions.values(\'id\', \'difficulty_rating\'))\r\n'
'\r\n'
'    # Select optimal first question\r\n'
'    selected = select_next_question(profile.elo_rating, all_questions)\r\n'
'    if not selected:\r\n'
"        return JsonResponse({'error': 'Could not select a question'}, status=500)\r\n"
'\r\n'
'    question = Question.objects.get(id=selected[\'id\'])\r\n'
'\r\n'
'    return JsonResponse({\r\n'
"        'success': True,\r\n"
'        \'session_id\': session.id,\r\n'
"        'document_id': doc_id,\r\n"
'        \'start_elo\': profile.elo_rating,\r\n'
"        'requested_questions': requested_n,\r\n"
"        'questions_to_answer': requested_n if requested_n is not None else questions.count(),\r\n"
"        'questions_generated': questions.count(),\r\n"
'        \'question\': {\r\n'
'            \'id\': question.id,\r\n'
"            'question_text': question.question_text,\r\n"
'            \'options\': question.options,\r\n'
"            'difficulty_label': question.difficulty_label,\r\n"
"            'difficulty_rating': question.difficulty_rating,\r\n"
'        },\r\n'
"        'total_questions_available': questions.count(),\r\n"
'    }, status=201)\r\n'
)

text = text[:start_idx] + new_block + text[end_idx:]

with open('pages/views.py','wb') as f:
    f.write(text.encode('utf-8'))

print("api_test_start rewritten")

# --- Now rewrite api_test_submit_answer tail ---

with open('pages/views.py','rb') as f:
    data = f.read()
text = data.decode('utf-8')

submit_tail_old = (
"    # Get next question\r\n"
"    answered_ids = session.responses.values_list('question_id', flat=True)\r\n"
"    available = Question.objects.filter(\r\n"
"        document=session.document\r\n"
"    ).exclude(id__in=answered_ids).values('id', 'difficulty_rating')\r\n"
"\r\n"
"    available_list = list(available)\r\n"
"    next_question = select_next_question(new_user_elo, available_list)\r\n"
"\r\n"
"    response_data = {\r\n"
"        'success': True,\r\n"
"        'is_correct': is_correct,\r\n"
"        'correct_index': question.correct_index,\r\n"
"        'explanation': question.explanation,\r\n"
"        'selected_index': int(selected_index),\r\n"
"        'user_elo_before': profile.elo_rating - (new_user_elo - profile.elo_rating),\r\n"
"        'user_elo_after': new_user_elo,\r\n"
"        'elo_change': new_user_elo - (profile.elo_rating - (new_user_elo - profile.elo_rating)),\r\n"
"        'question_difficulty': question.difficulty_label,\r\n"
"        'questions_answered': session.responses.count(),\r\n"
"        'total_available': Question.objects.filter(document=session.document).count(),\r\n"
"    }\r\n"
"\r\n"
"    if next_question:\r\n"
"        q = Question.objects.get(id=next_question['id'])\r\n"
"        response_data['next_question'] = {\r\n"
"            'id': q.id,\r\n"
"            'question_text': q.question_text,\r\n"
"            'options': q.options,\r\n"
"            'difficulty_label': q.difficulty_label,\r\n"
"            'difficulty_rating': q.difficulty_rating,\r\n"
"        }\r\n"
"    else:\r\n"
"        # Auto-complete if no more questions\r\n"
"        session.is_completed = True\r\n"
"        session.end_elo = new_user_elo\r\n"
"        session.save()\r\n"
"        response_data['session_completed'] = True\r\n"
"\r\n"
"    return JsonResponse(response_data, status=200)\r\n"
"\r\n"
"\r\n"
"@csrf_exempt\r\n"
"\r\n"
"\r\n"
"@csrf_exempt\r\n"
"\r\n"
"@api_view(['POST'])\r\n"
)

submit_tail_new = (
"    # Track how many questions this session has actually answered.\r\n"
"    session.questions_answered_count = session.responses.count()\r\n"
"    session.save(update_fields=['questions_answered_count'])\r\n"
"\r\n"
"    # Get next question from the remaining pool.\r\n"
"    answered_ids = session.responses.values_list('question_id', flat=True)\r\n"
"    available = Question.objects.filter(\r\n"
"        document=session.document\r\n"
"    ).exclude(id__in=answered_ids).values('id', 'difficulty_rating')\r\n"
"\r\n"
"    available_list = list(available)\r\n"
"    next_question = select_next_question(new_user_elo, available_list)\r\n"
"\r\n"
"    questions_to_answer = (\r\n"
"        session.requested_questions\r\n"
"        if session.requested_questions is not None\r\n"
"        else Question.objects.filter(document=session.document).count()\r\n"
"    )\r\n"
"\r\n"
"    response_data = {\r\n"
"        'success': True,\r\n"
"        'is_correct': is_correct,\r\n"
"        'correct_index': question.correct_index,\r\n"
"        'explanation': question.explanation,\r\n"
"        'selected_index': int(selected_index),\r\n"
"        'user_elo_before': profile.elo_rating - (new_user_elo - profile.elo_rating),\r\n"
"        'user_elo_after': new_user_elo,\r\n"
"        'elo_change': new_user_elo - (profile.elo_rating - (new_user_elo - profile.elo_rating)),\r\n"
"        'question_difficulty': question.difficulty_label,\r\n"
"        'questions_answered': session.questions_answered_count,\r\n"
"        'questions_to_answer': questions_to_answer,\r\n"
"        'questions_generated': session.questions_generated_count,\r\n"
"        'total_available': Question.objects.filter(document=session.document).count(),\r\n"
"    }\r\n"
"\r\n"
"    # End the session once the user has answered the requested N questions.\r\n"
"    # Legacy (no requested N) still ends when the pool is exhausted.\r\n"
"    if (\r\n"
"        session.requested_questions is not None\r\n"
"        and session.questions_answered_count >= session.requested_questions\r\n"
"    ):\r\n"
"        session.is_completed = True\r\n"
"        session.end_elo = new_user_elo\r\n"
"        session.save()\r\n"
"        response_data['session_completed'] = True\r\n"
"    elif next_question:\r\n"
"        q = Question.objects.get(id=next_question['id'])\r\n"
"        response_data['next_question'] = {\r\n"
"            'id': q.id,\r\n"
"            'question_text': q.question_text,\r\n"
"            'options': q.options,\r\n"
"            'difficulty_label': q.difficulty_label,\r\n"
"            'difficulty_rating': q.difficulty_rating,\r\n"
"        }\r\n"
"    else:\r\n"
"        session.is_completed = True\r\n"
"        session.end_elo = new_user_elo\r\n"
"        session.save()\r\n"
"        response_data['session_completed'] = True\r\n"
"        response_data['error'] = 'Question pool exhausted before completing the requested quiz.'\r\n"
"\r\n"
"    return JsonResponse(response_data, status=200)\r\n"
"\r\n"
"\r\n"
"@csrf_exempt\r\n"
"\r\n"
"@api_view(['POST'])\r\n"
)

assert submit_tail_old in text, "submit_tail_old not found verbatim"
text = text.replace(submit_tail_old, submit_tail_new)

with open('pages/views.py','wb') as f:
    f.write(text.encode('utf-8'))

print("api_test_submit_answer rewritten")
