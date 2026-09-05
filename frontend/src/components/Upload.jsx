import { useState, useRef } from 'react';
import { uploadDocument } from '../api';

export default function Upload({ onUpload }) {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  const handleDrop = (e) => {
    e.preventDefault();
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && droppedFile.name.toLowerCase().endsWith('.pdf')) {
      setFile(droppedFile);
      setError(null);
    } else {
      setError('Please select a PDF file');
    }
  };

  const handleFileSelect = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setError(null);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a PDF file');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await uploadDocument(file);
      onUpload(result.document_id, result.filename);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        style={{
          border: '1.5px dashed var(--card-border-strong)',
          background: 'var(--input-bg)',
          borderRadius: 'var(--radius-md)',
          padding: '2rem 1.5rem',
          textAlign: 'center',
          cursor: 'pointer',
          transition: 'border-color 0.25s ease, background 0.25s ease',
        }}
        onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent)'; }}
        onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--card-border-strong)'; }}
      >
        <div className="icon-tile" style={{ width: 52, height: 52, margin: '0 auto 0.9rem', fontSize: '1.4rem' }}>
          ☁️
        </div>
        <p style={{ fontSize: '0.9rem', fontWeight: 600 }}>
          {file ? file.name : 'Click to select or drag a PDF'}
        </p>
        <p className="t-caption" style={{ marginTop: '0.3rem', fontSize: '0.78rem' }}>
          PDF only · processed in under a minute
        </p>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />
      </div>

      {error && (
        <div
          style={{
            padding: '0.7rem 1rem',
            borderRadius: 'var(--radius-sm)',
            marginTop: '1rem',
            background: 'color-mix(in srgb, var(--danger) 10%, transparent)',
            border: '1px solid color-mix(in srgb, var(--danger) 30%, transparent)',
            color: 'var(--danger)',
            fontSize: '0.86rem',
          }}
        >
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="btn btn-primary"
        style={{ width: '100%', marginTop: '1.1rem', padding: '0.85rem' }}
      >
        {loading ? (
          <>
            <span
              className="spinner"
              style={{ width: 16, height: 16, borderWidth: 2, borderTopWidth: 2 }}
            />
            Processing…
          </>
        ) : (
          '✨ Process PDF'
        )}
      </button>
    </form>
  );
}
