export interface Department {
  id: number;
  name: string;
  area: string;
  website_url: string;
  email: string;
  phone: string;
  director: string;
  scraped_at: string;
}

export interface CdL {
  id: number;
  department_id: number;
  name: string;
  code: string;
  type: string;
  academic_year: string | null;
  url: string;
  scraped_at: string;
}

export interface SyllabusListItem {
  id: number;
  cdl_id: number;
  seuid: string;
  course_code: string;
  course_name: string;
  module: string | null;
  teacher: string;
  academic_year: string;
  year_of_study: string;
  url_it: string;
  url_en: string;
  has_english: boolean;
  scraped_at: string;
}

export interface SyllabusDetail extends SyllabusListItem {
  dublin_knowledge_it: string | null;
  dublin_applying_it: string | null;
  dublin_judgement_it: string | null;
  dublin_communication_it: string | null;
  dublin_learning_it: string | null;
  teaching_methods_it: string | null;
  prerequisites_it: string | null;
  attendance_it: string | null;
  course_content_it: string | null;
  references_it: string | null;
  schedule_it: ScheduleItem[] | null;
  assessment_methods_it: string | null;
  sample_questions_it: string | null;
  dublin_knowledge_en: string | null;
  dublin_applying_en: string | null;
  dublin_judgement_en: string | null;
  dublin_communication_en: string | null;
  dublin_learning_en: string | null;
  teaching_methods_en: string | null;
  prerequisites_en: string | null;
  attendance_en: string | null;
  course_content_en: string | null;
  references_en: string | null;
  schedule_en: ScheduleItem[] | null;
  assessment_methods_en: string | null;
  sample_questions_en: string | null;
  cdl_name: string | null;
  department_id: number | null;
  department_name: string | null;
}

export interface ScheduleItem {
  numero: string;
  argomenti: string;
  riferimenti_testi: string;
}

export interface Stats {
  departments: number;
  cdl: number;
  syllabi: number;
  with_english: number;
}

export interface JobCreated {
  job_id: string;
}

export interface SseProgress {
  type: "progress";
  current: number;
  total: number;
  message: string;
}

export interface SseDone {
  type: "done";
  scraped: number;
  errors: number;
}

export interface SseError {
  type: "error";
  message: string;
}

export type SseEvent = SseProgress | SseDone | SseError;
