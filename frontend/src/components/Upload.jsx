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
    <div>
      <h2 style={{ fontSize: '1.15rem', fontWeight: 600, marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        📄 Upload Study PDF
      </h2>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '1.25rem' }}>
          <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 500, color: '#94a3b8', marginBottom: '0.5rem' }}>
            Select Document (.pdf)
          </label>
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            style={{
              border: '2px dashed rgba(99,102,241,0.4)',
              background: 'rgba(99,102,241,0.05)',
              borderRadius: 12,
              padding: '1.5rem',
              textAlign: 'center',
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
          >
            <div style={{ fontSize: '2.5rem', color: '#6366f1', marginBottom: '0.75rem' }}>☁️</div>
            <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
              {file ? file.name : 'Click to select or drag PDF file'}
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />
          </div>
        </div>

        {error && (
          <div style={{
            padding: '0.75rem 1rem', borderRadius: 10, marginBottom: '1.25rem',
            background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)',
            color: '#fca5a5', fontSize: '0.9rem',
          }}>
            {error}
          </div>
        )}

        <button type="submit" disabled={loading} style={{
          width: '100%', padding: '0.875rem',
          background: loading ? 'rgba(99,102,241,0.5)' : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
          border: 'none', borderRadius: 10, color: 'white', fontWeight: 600, fontSize: '0.95rem',
          cursor: loading ? 'not-allowed' : 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
        }}>
          {loading ? '⬆️ Uploading...' : '✨ Process PDF'}
        </button>
      </form>
    </div>
  );
}
