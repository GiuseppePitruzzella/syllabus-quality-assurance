import { useState, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { scrapeSyllabusDetail } from "@/lib/api";
import type { SyllabusDetail } from "@/lib/types";

export function useAutoScrape(data: SyllabusDetail | undefined) {
  const [isLoading, setIsLoading] = useState(false);
  const queryClient = useQueryClient();
  const triggered = useRef(false);

  useEffect(() => {
    if (!data || triggered.current) return;

    const isEmpty =
      !data.dublin_knowledge_it &&
      !data.dublin_applying_it &&
      !data.dublin_judgement_it &&
      !data.dublin_communication_it &&
      !data.dublin_learning_it;

    if (!isEmpty) return;

    triggered.current = true;
    setIsLoading(true);

    scrapeSyllabusDetail(data.seuid)
      .then(() => {
        queryClient.invalidateQueries({ queryKey: ["syllabus", data.seuid] });
      })
      .finally(() => setIsLoading(false));
  }, [data, queryClient]);

  return { isLoading };
}
