from django import forms
from .models import UploadedPDF


class PDFUploadForm(forms.ModelForm):
    api_key = forms.CharField(
        required=False,
        label="Gemini API Key (Optional - preconfigured)",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Leave blank to use preconfigured system key'
        })
    )

    class Meta:
        model = UploadedPDF
        fields = ['file']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf'
            })
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if not file.name.lower().endswith('.pdf'):
                raise forms.ValidationError("Only PDF files are supported.")
        return file
