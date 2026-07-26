"use client";

interface SuggestedPromptsProps {
  onSelect: (prompt: string) => void;
  disabled?: boolean;
}

const PROMPTS = [
  "Incorporate my private limited company",
  "File my Q4 GST return",
  "Help me get a Shops & Establishment license",
];

export function SuggestedPrompts({ onSelect, disabled }: SuggestedPromptsProps) {
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">Try one of these:</p>
      <div className="flex flex-col gap-2">
        {PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(prompt)}
            className="rounded-lg border border-border bg-background px-3 py-2 text-left text-sm text-foreground transition hover:bg-accent disabled:opacity-50"
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}
