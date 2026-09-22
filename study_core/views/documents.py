"""Document content-generation views (upload / summary / flashcards)."""

from django.http import Http404
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Document, Flashcard
from ..serializers import (
    DocumentSerializer,
    FlashcardSerializer,
    UploadDocumentSerializer,
)
from ..services import llm_service
from ..services.pdf_parser import extract_text_from_pdf
from .common import _get_user


def _get_document_for_user_or_404(doc_id, request):
    """Return the requesting user's Document or raise 404."""
    try:
        return Document.objects.get(id=doc_id, user=_get_user(request))
    except Document.DoesNotExist:
        raise Http404('Document not found.')


class UploadDocumentView(APIView):
    """POST /api/v2/documents/upload/ — Upload PDF, parse text."""

    def post(self, request):
        serializer = UploadDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = _get_user(request)
        pdf_file = serializer.validated_data['file']

        doc = Document.objects.create(
            user=user,
            file=pdf_file,
            filename=pdf_file.name,
        )

        try:
            extracted_text = extract_text_from_pdf(doc.file.path)
            if not extracted_text.strip():
                raise ValueError("Extracted text from PDF is empty.")
            doc.raw_text = extracted_text
            doc.save()
        except Exception as e:
            return Response(
                {'error': f'Failed to process PDF: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            DocumentSerializer(doc).data,
            status=status.HTTP_201_CREATED,
        )


def _document_text(doc):
    """Raw text for generation, re-extracting from the PDF when needed."""
    text = doc.raw_text
    if not text or not text.strip():
        text = extract_text_from_pdf(doc.file.path)
        doc.raw_text = text or ''
        doc.save(update_fields=['raw_text'])
    if not text or not text.strip():
        raise ValueError("Document has no extractable text.")
    return text


class DocumentSummaryView(APIView):
    """GET /api/v2/documents/<uuid>/summary/ — Generate/return structured summary."""

    def get(self, request, doc_id):
        doc = _get_document_for_user_or_404(doc_id, request)

        # Return cached summary if available
        if doc.summary_data:
            return Response(doc.summary_data)

        try:
            text = _document_text(doc)
            summary_data = llm_service.generate_summary(text=text)
            doc.summary_data = summary_data
            doc.save()

            return Response(summary_data)
        except Exception as e:
            return Response(
                {'error': f'Failed to generate summary: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DocumentFlashcardsView(APIView):
    """GET /api/v2/documents/<uuid>/flashcards/ — Generate/return 20 flashcards."""

    def get(self, request, doc_id):
        doc = _get_document_for_user_or_404(doc_id, request)

        # Return cached flashcards if available
        cached = doc.flashcards.all()
        if cached.exists():
            return Response(FlashcardSerializer(cached, many=True).data)

        try:
            text = _document_text(doc)
            cards_data = llm_service.generate_flashcards(text=text)
            flashcard_objects = [
                Flashcard(document=doc, front=c['front'], back=c['back'])
                for c in cards_data
            ]
            Flashcard.objects.bulk_create(flashcard_objects)

            return Response(
                FlashcardSerializer(doc.flashcards.all(), many=True).data
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to generate flashcards: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
