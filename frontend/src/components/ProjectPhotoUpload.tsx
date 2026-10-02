import { useEffect, useRef, useState } from 'react';
import type { DragEvent } from 'react';

const MAX_FILE_BYTES = 10 * 1024 * 1024;

type PhotoUploadProps = {
  photo?: File | null;
  onPhotoChange?: (photo: File | null) => void;
  onValidationChange?: (message: string) => void;
  validationMessage?: string;
  disabled?: boolean;
};

export function ProjectPhotoUpload({ photo: selectedPhoto, onPhotoChange, onValidationChange, validationMessage, disabled = false }: PhotoUploadProps = {}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [localPhoto, setLocalPhoto] = useState<File | null>(null);
  const photo = selectedPhoto === undefined ? localPhoto : selectedPhoto;
  const [preview, setPreview] = useState('');
  const [localError, setError] = useState('');
  const error = validationMessage === undefined ? localError : validationMessage;
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    if (!photo) { setPreview(''); return; }
    const url = URL.createObjectURL(photo);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [photo]);

  function acceptPhoto(file?: File) {
    if (disabled) return;
    setError('');
    onValidationChange?.('');
    if (!file) return;
    if (!['image/jpeg', 'image/png'].includes(file.type)) {
      const message = 'Choose a JPG or PNG image.';
      setError(message);
      onValidationChange?.(message);
      if (inputRef.current) inputRef.current.value = '';
      setLocalPhoto(null);
      onPhotoChange?.(null);
      return;
    }
    if (file.size === 0 || file.size > MAX_FILE_BYTES) {
      const message = file.size === 0 ? 'This image is empty. Choose another photo.' : 'This image is larger than 10 MB. Choose a smaller photo.';
      setError(message);
      onValidationChange?.(message);
      if (inputRef.current) inputRef.current.value = '';
      setLocalPhoto(null);
      onPhotoChange?.(null);
      return;
    }
    setLocalPhoto(file);
    onPhotoChange?.(file);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    if (disabled) return;
    setDragging(false);
    const dropped = event.dataTransfer.files?.[0];
    if (!dropped) return;
    if (inputRef.current) {
      const transfer = new DataTransfer();
      transfer.items.add(dropped);
      inputRef.current.files = transfer.files;
    }
    acceptPhoto(dropped);
  }

  function clearPhoto() {
    if (inputRef.current) inputRef.current.value = '';
    setLocalPhoto(null);
    onPhotoChange?.(null);
    setError('');
    onValidationChange?.('');
  }

  return (
    <div
      className={`ss-photo-upload${dragging ? ' is-dragging' : ''}${photo ? ' has-photo' : ''}`}
      onDragOver={(event) => { event.preventDefault(); if (!disabled) setDragging(true); }}
      onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragging(false); }}
      onDrop={handleDrop}
    >
      <input
        ref={inputRef}
        id="roomPhotoInput"
        name="roomPhoto"
        className="ss-photo-upload__input"
        type="file"
        disabled={disabled}
        accept="image/jpeg,image/png"
        aria-describedby="ss-photo-help ss-photo-error"
        onChange={(event) => acceptPhoto(event.currentTarget.files?.[0])}
      />
      <label className="ss-photo-upload__picker" htmlFor="roomPhotoInput">
        <span className="ss-photo-upload__icon" aria-hidden="true">＋</span>
        <span className="ss-photo-upload__copy">
          <strong>{photo ? photo.name : 'Choose a room photo'}</strong>
          <small>{photo ? 'Photo attached for object detection' : 'Drop a JPG or PNG here, or browse your device'}</small>
        </span>
        <span className="ss-photo-upload__browse">Browse</span>
      </label>
      <p id="ss-photo-help" className="ss-photo-upload__hint">Optional · JPG or PNG · Up to 10 MB. YOLO will map recognized objects to the room plan. Without a usable photo, SmartSpace starts with room-type furniture.</p>
      {preview && (
        <div className="ss-photo-upload__preview">
          <img src={preview} alt="Preview of the selected room" />
          <button type="button" onClick={clearPhoto} disabled={disabled} aria-label="Remove selected room photo">Remove photo</button>
        </div>
      )}
      {error && <div><p id="ss-photo-error" className="ss-photo-upload__error" role="alert">{error}</p>
        <button type="button" onClick={clearPhoto} disabled={disabled}>Continue without a photo</button>
      </div>}
    </div>
  );
}
