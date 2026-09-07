"""Archive the legacy `pages` app database tables.

The `pages` app is being removed (its models/views are superseded by
study_core and its referenced data was consolidated in the previous
migration). The old tables are renamed to archive_pages_* rather than
dropped, so every historical row stays recoverable while clearly being
out of the way.

Reversible: the reverse operation renames them back.
"""

from django.db import migrations


LEGACY_TABLES = [
    "pages_uploadedpdf",
    "pages_userprofile",
    "pages_question",
    "pages_flashcard",
    "pages_summary",
    "pages_testsession",
    "pages_sessionresponse",
]


class Migration(migrations.Migration):

    dependencies = [
        ("study_core", "0014_consolidate_pages_data"),
    ]

    operations = [
        migrations.RunSQL(
            sql="\n".join(
                f"ALTER TABLE IF EXISTS {t} RENAME TO archive_{t};"
                for t in LEGACY_TABLES
            ),
            reverse_sql="\n".join(
                f"ALTER TABLE IF EXISTS archive_{t} RENAME TO {t};"
                for t in LEGACY_TABLES
            ),
        ),
    ]
