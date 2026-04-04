import { useParams } from "react-router-dom";

export function SyllabusViewer() {
  const { seuid } = useParams<{ seuid: string }>();
  return (
    <div>
      <h1 className="text-2xl font-bold">Syllabus Viewer</h1>
      <p className="text-muted-foreground mt-2">seuid: {seuid}</p>
    </div>
  );
}
