"""Consolidate legacy `pages` app data into `study_core`.

Copies the legacy pages_* rows that carry real user data into the
study_core_* tables (which are the single source of truth), so that the
`pages` app can be removed without losing anything:

- UploadedPDF (referenced by sessions / flashcards / summaries)
      -> study_core.Document        (owner from the legacy session, else an
                                     existing Document with the same file,
                                     else the first superuser)
- Question (only for documents that have quiz-session history)
      -> study_core.Question        (text-normalised dedup per document)
- Flashcard
      -> study_core.Flashcard       (dedup per document by card front)
- Summary
      -> Document.summary_data JSON (study_core has no separate Summary model)
- TestSession + SessionResponse
      -> study_core equivalents     (ids remapped, answered_at preserved)

Legacy rows that are regenerable LLM output with no user data (question banks
belonging to ownerless one-off uploads) are NOT copied — they stay in the
archived legacy tables created by the follow-up migration.

Runs as raw SQL against the legacy tables so it works even though the `pages`
app is about to be removed, and no-ops on fresh databases that never had it.
"""

import json
import uuid

from django.db import connection, migrations


def _norm(text):
    """Lowercase, whitespace-stripped key for text dedup."""
    return "".join(str(text or "").lower().split())


def consolidate_pages_data(apps, schema_editor):
    cursor = connection.cursor()

    # Fresh databases never had the pages app — nothing to consolidate.
    cursor.execute("SELECT to_regclass('pages_uploadedpdf')")
    if cursor.fetchone()[0] is None:
        cursor.close()
        return

    # ── 1. Legacy documents referenced by real user data ────────────────
    cursor.execute(
        """
        SELECT DISTINCT document_id FROM pages_testsession
        UNION
        SELECT DISTINCT document_id FROM pages_flashcard
        UNION
        SELECT DISTINCT document_id FROM pages_summary
        """
    )
    referenced = [r[0] for r in cursor.fetchall()]
    if not referenced:
        cursor.close()
        return

    # Fallback owner: first superuser, else first user.
    cursor.execute(
        "SELECT id FROM auth_user ORDER BY is_superuser DESC, id LIMIT 1"
    )
    fallback_owner = cursor.fetchone()[0]

    # Owner of the legacy session held for each document (if any).
    cursor.execute(
        "SELECT DISTINCT ON (document_id) document_id, user_id "
        "FROM pages_testsession WHERE user_id IS NOT NULL"
    )
    session_owner = dict(cursor.fetchall())

    doc_map = {}
    for old_id in referenced:
        cursor.execute(
            "SELECT file, raw_text FROM pages_uploadedpdf WHERE id = %s",
            [old_id],
        )
        row = cursor.fetchone()
        if row is None:
            continue
        file_name, raw_text = row[0], row[1] or ""

        # Reuse an existing study_core Document for the same file if present.
        cursor.execute(
            "SELECT id FROM study_core_document "
            "WHERE filename = %s ORDER BY created_at LIMIT 1",
            [file_name],
        )
        existing = cursor.fetchone()
        if existing:
            doc_map[old_id] = existing[0]
            continue

        new_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO study_core_document
                (id, user_id, file, filename, raw_text, summary_data, created_at)
            VALUES (%s, %s, %s, %s, %s, '{}'::jsonb, NOW())
            """,
            [new_id, session_owner.get(old_id) or fallback_owner,
             file_name, file_name, raw_text],
        )
        doc_map[old_id] = new_id

    # ── 2. Question banks — only for documents with quiz-session history ─
    cursor.execute("SELECT DISTINCT document_id FROM pages_testsession")
    session_docs = [r[0] for r in cursor.fetchall()]

    q_map = {}
    for old_doc in session_docs:
        new_doc = doc_map.get(old_doc)
        if not new_doc:
            continue
        cursor.execute(
            """
            SELECT id, question_text, options, correct_index, explanation,
                   difficulty_rating, times_served, times_correct
            FROM pages_question WHERE document_id = %s
            """,
            [old_doc],
        )
        for (old_q, text, options, idx, expl, rating,
             served, correct) in cursor.fetchall():
            cursor.execute(
                "SELECT id FROM study_core_question "
                "WHERE document_id = %s AND regexp_replace("
                "lower(question_text), '\\s+', '', 'g') = %s LIMIT 1",
                [new_doc, _norm(text)],
            )
            found = cursor.fetchone()
            if found:
                q_map[old_q] = found[0]
                continue
            new_q = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO study_core_question
                    (id, document_id, question_text, options, correct_index,
                     explanation, difficulty_rating, times_served, times_correct)
                VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
                """,
                [new_q, new_doc, text, json.dumps(options), idx, expl,
                 rating, served, correct],
            )
            q_map[old_q] = new_q

    # ── 3. Flashcards ────────────────────────────────────────────────────
    for old_doc, new_doc in doc_map.items():
        cursor.execute(
            'SELECT front, back FROM pages_flashcard '
            'WHERE document_id = %s ORDER BY "order", id',
            [old_doc],
        )
        for front, back in cursor.fetchall():
            cursor.execute(
                "SELECT 1 FROM study_core_flashcard "
                "WHERE document_id = %s AND front = %s LIMIT 1",
                [new_doc, front],
            )
            if cursor.fetchone():
                continue
            cursor.execute(
                "INSERT INTO study_core_flashcard (id, document_id, front, back) "
                "VALUES (%s, %s, %s, %s)",
                [str(uuid.uuid4()), new_doc, front, back],
            )

    # ── 4. Summaries → Document.summary_data ─────────────────────────────
    for old_doc, new_doc in doc_map.items():
        cursor.execute(
            "SELECT executive_summary, key_concepts, terminology "
            "FROM pages_summary WHERE document_id = %s LIMIT 1",
            [old_doc],
        )
        row = cursor.fetchone()
        if not row:
            continue
        summary_payload = json.dumps({
            "executive_summary": row[0] or "",
            "key_concepts": row[1] or [],
            "terminology": row[2] or [],
        })
        cursor.execute(
            """
            UPDATE study_core_document
            SET summary_data = %s::jsonb
            WHERE id = %s
              AND (summary_data IS NULL OR summary_data = '{}'::jsonb)
            """,
            [summary_payload, new_doc],
        )

    # ── 5. Test sessions + responses ─────────────────────────────────────
    sess_map = {}
    cursor.execute(
        "SELECT id, user_id, document_id, start_elo, end_elo, is_completed, "
        "created_at FROM pages_testsession"
    )
    sessions = cursor.fetchall()
    for ts_id, user_id, old_doc, start_elo, end_elo, completed, created in sessions:
        new_doc = doc_map.get(old_doc)
        if not new_doc:
            continue
        cursor.execute(
            "SELECT COUNT(*) FROM pages_sessionresponse WHERE session_id = %s",
            [ts_id],
        )
        answered = cursor.fetchone()[0]
        cursor.execute(
            "SELECT COUNT(*) FROM study_core_question WHERE document_id = %s",
            [new_doc],
        )
        generated = cursor.fetchone()[0]
        new_sid = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO study_core_testsession
                (id, user_id, document_id, start_elo, end_elo, persona_tier,
                 requested_questions, generated_questions, is_completed, created_at)
            VALUES (%s, %s, %s, %s, %s, 'Beginner', %s, %s, %s, %s)
            """,
            [new_sid, user_id, new_doc, start_elo, end_elo,
             answered, generated, completed, created],
        )
        sess_map[ts_id] = new_sid

    cursor.execute(
        "SELECT session_id, question_id, selected_index, is_correct, "
        "time_taken_sec, user_elo_after, answered_at FROM pages_sessionresponse"
    )
    responses = cursor.fetchall()
    for old_sid, old_q, sel, ok, secs, elo_after, answered_at in responses:
        new_sid = sess_map.get(old_sid)
        new_q = q_map.get(old_q)
        if not new_sid or not new_q:
            continue
        cursor.execute(
            "SELECT 1 FROM study_core_sessionresponse "
            "WHERE session_id = %s AND question_id = %s LIMIT 1",
            [new_sid, new_q],
        )
        if cursor.fetchone():
            continue
        cursor.execute(
            """
            INSERT INTO study_core_sessionresponse
                (id, session_id, question_id, selected_index, is_correct,
                 time_taken_sec, user_elo_after, question_elo_after, answered_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 0.0, %s)
            """,
            [str(uuid.uuid4()), new_sid, new_q, sel, ok, secs,
             elo_after, answered_at],
        )

    cursor.close()


class Migration(migrations.Migration):

    dependencies = [
        ("study_core", "0013_add_sessionresponse_answered_at"),
    ]

    operations = [
        migrations.RunPython(consolidate_pages_data, migrations.RunPython.noop),
    ]
