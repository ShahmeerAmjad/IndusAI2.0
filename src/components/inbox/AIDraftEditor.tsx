import { useState } from "react";
import { Pencil, Check, X } from "lucide-react";

interface AIDraftEditorProps {
  draft: string;
  onSave: (text: string) => void;
  disabled?: boolean;
}

export default function AIDraftEditor({ draft, onSave, disabled }: AIDraftEditorProps) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(draft);

  const handleSave = () => {
    onSave(text);
    setEditing(false);
  };

  const handleCancel = () => {
    setText(draft);
    setEditing(false);
  };

  if (!editing) {
    return (
      <div className="group relative rounded-lg border border-neutral-200 bg-white p-4">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-neutral-700">AI Draft Response</h3>
          {!disabled && (
            <button
              onClick={() => setEditing(true)}
              className="flex items-center gap-1 rounded px-2 py-1 text-xs text-neutral-500 opacity-0 transition hover:bg-neutral-100 group-hover:opacity-100"
            >
              <Pencil size={12} /> Edit
            </button>
          )}
        </div>
        <div className="whitespace-pre-wrap text-sm text-neutral-600 leading-relaxed">
          {draft || <span className="italic text-neutral-400">No draft generated yet</span>}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border-2 border-industrial-300 bg-white p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-industrial-700">Editing Draft</h3>
        <div className="flex gap-1">
          <button
            onClick={handleSave}
            className="flex items-center gap-1 rounded bg-industrial-600 px-2 py-1 text-xs text-white hover:bg-industrial-700"
          >
            <Check size={12} /> Save
          </button>
          <button
            onClick={handleCancel}
            className="flex items-center gap-1 rounded border px-2 py-1 text-xs text-neutral-600 hover:bg-neutral-50"
          >
            <X size={12} /> Cancel
          </button>
        </div>
      </div>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={10}
        className="w-full rounded border border-neutral-300 p-3 text-sm focus:border-industrial-400 focus:outline-none focus:ring-1 focus:ring-industrial-400"
      />
    </div>
  );
}
