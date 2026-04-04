import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { getSyllabus } from "@/lib/api";
import type { SyllabusDetail } from "@/lib/types";
import { useAutoScrape } from "@/hooks/useAutoScrape";
import { Breadcrumb } from "@/components/Breadcrumb";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { DublinDescriptors } from "./DublinDescriptors";
import { CourseScheduleTable } from "./CourseScheduleTable";
import { MetadataSidebar } from "./MetadataSidebar";

function LangToggle({
  lang,
  setLang,
  hasEnglish,
}: {
  lang: "it" | "en";
  setLang: (l: "it" | "en") => void;
  hasEnglish: boolean;
}) {
  return (
    <div className="flex gap-1">
      <Button
        size="sm"
        variant={lang === "it" ? "default" : "ghost"}
        onClick={() => setLang("it")}
      >
        IT
      </Button>
      {hasEnglish ? (
        <Button
          size="sm"
          variant={lang === "en" ? "default" : "ghost"}
          onClick={() => setLang("en")}
        >
          EN
        </Button>
      ) : (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger
              render={
                <Button size="sm" variant="ghost" disabled>
                  EN
                </Button>
              }
            />
            <TooltipContent>
              Versione inglese non disponibile
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
    </div>
  );
}

export function SyllabusViewer() {
  const { seuid } = useParams<{ seuid: string }>();
  const [lang, setLang] = useState<"it" | "en">("it");

  const { data, isLoading } = useQuery({
    queryKey: ["syllabus", seuid],
    queryFn: () => getSyllabus(seuid!),
    enabled: !!seuid,
  });

  const autoScrape = useAutoScrape(data);

  if (isLoading) {
    return <p className="text-muted-foreground">Caricamento...</p>;
  }

  if (!data) {
    return <p className="text-muted-foreground">Syllabus non trovato.</p>;
  }

  if (autoScrape.isLoading) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-20">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-muted-foreground">
          Scaricamento contenuto in corso...
        </p>
      </div>
    );
  }

  const textField = (field: string): string => {
    const key = `${field}_${lang}` as keyof SyllabusDetail;
    return (data[key] as string) || "";
  };

  const breadcrumbItems = [
    {
      label: data.department_name ?? "Dipartimento",
      to: `/?dept=${data.department_id}`,
    },
    {
      label: data.cdl_name ?? "CdL",
      to: `/?dept=${data.department_id}&cdl=${data.cdl_id}`,
    },
    { label: data.course_name },
  ];

  return (
    <div>
      <Breadcrumb items={breadcrumbItems} />

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">{data.course_name}</h1>
        <LangToggle
          lang={lang}
          setLang={setLang}
          hasEnglish={data.has_english}
        />
      </div>

      <div className="flex gap-6">
        <div className="flex-1 min-w-0">
          <Tabs defaultValue="obiettivi">
            <TabsList>
              <TabsTrigger value="obiettivi">Obiettivi Formativi</TabsTrigger>
              <TabsTrigger value="contenuto">
                Contenuto e Programma
              </TabsTrigger>
              <TabsTrigger value="metodologia">Metodologia</TabsTrigger>
              <TabsTrigger value="verifica">Verifica</TabsTrigger>
              <TabsTrigger value="risorse">Risorse</TabsTrigger>
            </TabsList>

            <TabsContent value="obiettivi" className="mt-4">
              <DublinDescriptors data={data} lang={lang} />
            </TabsContent>

            <TabsContent value="contenuto" className="mt-4 space-y-6">
              <div>
                <h3 className="font-semibold mb-2">Contenuto del corso</h3>
                <p className="text-muted-foreground whitespace-pre-line">
                  {textField("course_content") || "\u2014"}
                </p>
              </div>
              <div>
                <h3 className="font-semibold mb-2">Programmazione</h3>
                <CourseScheduleTable
                  items={
                    lang === "it" ? data.schedule_it : data.schedule_en
                  }
                />
              </div>
            </TabsContent>

            <TabsContent value="metodologia" className="mt-4 space-y-6">
              <div>
                <h3 className="font-semibold mb-2">Metodi di insegnamento</h3>
                <p className="text-muted-foreground whitespace-pre-line">
                  {textField("teaching_methods") || "\u2014"}
                </p>
              </div>
              <div>
                <h3 className="font-semibold mb-2">Frequenza</h3>
                <p className="text-muted-foreground whitespace-pre-line">
                  {textField("attendance") || "\u2014"}
                </p>
              </div>
              <div>
                <h3 className="font-semibold mb-2">Prerequisiti</h3>
                <p className="text-muted-foreground whitespace-pre-line">
                  {textField("prerequisites") || "\u2014"}
                </p>
              </div>
            </TabsContent>

            <TabsContent value="verifica" className="mt-4 space-y-6">
              <div>
                <h3 className="font-semibold mb-2">Metodi di valutazione</h3>
                <p className="text-muted-foreground whitespace-pre-line">
                  {textField("assessment_methods") || "\u2014"}
                </p>
              </div>
              <div>
                <h3 className="font-semibold mb-2">Domande di esempio</h3>
                <p className="text-muted-foreground whitespace-pre-line">
                  {textField("sample_questions") || "\u2014"}
                </p>
              </div>
            </TabsContent>

            <TabsContent value="risorse" className="mt-4">
              <div>
                <h3 className="font-semibold mb-2">Riferimenti</h3>
                <p className="text-muted-foreground whitespace-pre-line">
                  {textField("references") || "\u2014"}
                </p>
              </div>
            </TabsContent>
          </Tabs>
        </div>

        <MetadataSidebar data={data} />
      </div>
    </div>
  );
}
