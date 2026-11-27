export type Status = { kind: "ok" | "error"; text: string } | null;

export function Notice({ status, onClose }: { status: Status; onClose: () => void }) {
  if (!status) return null;
  return (
    <p className={status.kind === "error" ? "error" : "ok"}>
      {status.text} <button className="link" onClick={onClose}>×</button>
    </p>
  );
}
