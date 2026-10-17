// GENERADO AUTOMATICAMENTE. No editar a mano.
//
// Tipos TypeScript del esquema real de Supabase (proyecto proctoring,
// ref uzuysjmymvtpoxfrdxnm). Los usan apps/web y apps/desktop para tener
// autocompletado y comprobacion de tipos contra las tablas.
//
// Regenerar despues de cada migracion:
//   npx supabase gen types typescript --project-id uzuysjmymvtpoxfrdxnm > packages/contracts/database.types.ts
//
// Uso:
//   import { createClient } from '@supabase/supabase-js';
//   import type { Database } from '@proctoring/contracts/database.types';
//   const supabase = createClient<Database>(url, publishableKey);

export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.18"
  }
  public: {
    Tables: {
      alerts: {
        Row: {
          created_at: string
          event_id: string
          id: string
          reason: string
          session_id: string
          severity: Database["public"]["Enums"]["alert_severity"]
          student_id: string
        }
        Insert: {
          created_at?: string
          event_id: string
          id?: string
          reason: string
          session_id: string
          severity: Database["public"]["Enums"]["alert_severity"]
          student_id: string
        }
        Update: {
          created_at?: string
          event_id?: string
          id?: string
          reason?: string
          session_id?: string
          severity?: Database["public"]["Enums"]["alert_severity"]
          student_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "alerts_event_id_fkey"
            columns: ["event_id"]
            isOneToOne: false
            referencedRelation: "events"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "alerts_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "exam_sessions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "alerts_student_id_fkey"
            columns: ["student_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      answers: {
        Row: {
          answered_at: string
          id: string
          is_correct: boolean | null
          numeric_answer: number | null
          participant_id: string
          points_awarded: number | null
          question_id: string
          selected_option_id: string | null
          text_answer: string | null
        }
        Insert: {
          answered_at?: string
          id?: string
          is_correct?: boolean | null
          numeric_answer?: number | null
          participant_id: string
          points_awarded?: number | null
          question_id: string
          selected_option_id?: string | null
          text_answer?: string | null
        }
        Update: {
          answered_at?: string
          id?: string
          is_correct?: boolean | null
          numeric_answer?: number | null
          participant_id?: string
          points_awarded?: number | null
          question_id?: string
          selected_option_id?: string | null
          text_answer?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "answers_participant_id_fkey"
            columns: ["participant_id"]
            isOneToOne: false
            referencedRelation: "session_participants"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "answers_question_id_fkey"
            columns: ["question_id"]
            isOneToOne: false
            referencedRelation: "questions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "answers_selected_option_id_fkey"
            columns: ["selected_option_id"]
            isOneToOne: false
            referencedRelation: "question_options"
            referencedColumns: ["id"]
          },
        ]
      }
      audio_analyses: {
        Row: {
          event_id: string
          id: string
          matched_question_id: string | null
          model_versions: Json
          processed_at: string
          processing_ms: number | null
          similarity: number | null
          synthetic_voice_score: number | null
          transcript: string | null
        }
        Insert: {
          event_id: string
          id?: string
          matched_question_id?: string | null
          model_versions?: Json
          processed_at?: string
          processing_ms?: number | null
          similarity?: number | null
          synthetic_voice_score?: number | null
          transcript?: string | null
        }
        Update: {
          event_id?: string
          id?: string
          matched_question_id?: string | null
          model_versions?: Json
          processed_at?: string
          processing_ms?: number | null
          similarity?: number | null
          synthetic_voice_score?: number | null
          transcript?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "audio_analyses_event_id_fkey"
            columns: ["event_id"]
            isOneToOne: true
            referencedRelation: "events"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "audio_analyses_matched_question_id_fkey"
            columns: ["matched_question_id"]
            isOneToOne: false
            referencedRelation: "questions"
            referencedColumns: ["id"]
          },
        ]
      }
      course_enrollments: {
        Row: {
          course_id: string
          enrolled_at: string
          student_id: string
        }
        Insert: {
          course_id: string
          enrolled_at?: string
          student_id: string
        }
        Update: {
          course_id?: string
          enrolled_at?: string
          student_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "course_enrollments_course_id_fkey"
            columns: ["course_id"]
            isOneToOne: false
            referencedRelation: "courses"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "course_enrollments_student_id_fkey"
            columns: ["student_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      courses: {
        Row: {
          created_at: string
          id: string
          name: string
          section: string | null
          teacher_id: string
        }
        Insert: {
          created_at?: string
          id?: string
          name: string
          section?: string | null
          teacher_id: string
        }
        Update: {
          created_at?: string
          id?: string
          name?: string
          section?: string | null
          teacher_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "courses_teacher_id_fkey"
            columns: ["teacher_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      decisions: {
        Row: {
          decided_at: string
          decision: Database["public"]["Enums"]["decision_type"]
          id: string
          justification: string
          session_id: string
          student_id: string
          teacher_id: string
        }
        Insert: {
          decided_at?: string
          decision: Database["public"]["Enums"]["decision_type"]
          id?: string
          justification: string
          session_id: string
          student_id: string
          teacher_id: string
        }
        Update: {
          decided_at?: string
          decision?: Database["public"]["Enums"]["decision_type"]
          id?: string
          justification?: string
          session_id?: string
          student_id?: string
          teacher_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "decisions_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "exam_sessions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "decisions_student_id_fkey"
            columns: ["student_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "decisions_teacher_id_fkey"
            columns: ["teacher_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      events: {
        Row: {
          created_at: string
          duration_ms: number
          event_type: Database["public"]["Enums"]["event_type"]
          evidence_path: string | null
          id: string
          metadata: Json
          question_id: string | null
          session_id: string
          started_at: string
          student_id: string
        }
        Insert: {
          created_at?: string
          duration_ms?: number
          event_type: Database["public"]["Enums"]["event_type"]
          evidence_path?: string | null
          id?: string
          metadata?: Json
          question_id?: string | null
          session_id: string
          started_at: string
          student_id: string
        }
        Update: {
          created_at?: string
          duration_ms?: number
          event_type?: Database["public"]["Enums"]["event_type"]
          evidence_path?: string | null
          id?: string
          metadata?: Json
          question_id?: string | null
          session_id?: string
          started_at?: string
          student_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "events_question_id_fkey"
            columns: ["question_id"]
            isOneToOne: false
            referencedRelation: "questions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "events_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "exam_sessions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "events_student_id_fkey"
            columns: ["student_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      exam_sessions: {
        Row: {
          access_code: string
          allow_back_navigation: boolean
          course_id: string | null
          created_at: string
          description: string | null
          duration_minutes: number
          entry_tolerance_minutes: number
          id: string
          max_attempts: number
          preset: Database["public"]["Enums"]["supervision_preset"]
          question_pool_size: number | null
          reveal_code_at_start: boolean
          show_answers_at: string | null
          shuffle_options: boolean
          shuffle_questions: boolean
          starts_at: string
          status: Database["public"]["Enums"]["session_status"]
          teacher_id: string
          title: string
          updated_at: string
        }
        Insert: {
          access_code: string
          allow_back_navigation?: boolean
          course_id?: string | null
          created_at?: string
          description?: string | null
          duration_minutes: number
          entry_tolerance_minutes?: number
          id?: string
          max_attempts?: number
          preset?: Database["public"]["Enums"]["supervision_preset"]
          question_pool_size?: number | null
          reveal_code_at_start?: boolean
          show_answers_at?: string | null
          shuffle_options?: boolean
          shuffle_questions?: boolean
          starts_at: string
          status?: Database["public"]["Enums"]["session_status"]
          teacher_id: string
          title: string
          updated_at?: string
        }
        Update: {
          access_code?: string
          allow_back_navigation?: boolean
          course_id?: string | null
          created_at?: string
          description?: string | null
          duration_minutes?: number
          entry_tolerance_minutes?: number
          id?: string
          max_attempts?: number
          preset?: Database["public"]["Enums"]["supervision_preset"]
          question_pool_size?: number | null
          reveal_code_at_start?: boolean
          show_answers_at?: string | null
          shuffle_options?: boolean
          shuffle_questions?: boolean
          starts_at?: string
          status?: Database["public"]["Enums"]["session_status"]
          teacher_id?: string
          title?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "exam_sessions_course_id_fkey"
            columns: ["course_id"]
            isOneToOne: false
            referencedRelation: "courses"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "exam_sessions_teacher_id_fkey"
            columns: ["teacher_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      profiles: {
        Row: {
          created_at: string
          email: string | null
          full_name: string
          id: string
          role: Database["public"]["Enums"]["user_role"]
          student_code: string | null
        }
        Insert: {
          created_at?: string
          email?: string | null
          full_name: string
          id: string
          role?: Database["public"]["Enums"]["user_role"]
          student_code?: string | null
        }
        Update: {
          created_at?: string
          email?: string | null
          full_name?: string
          id?: string
          role?: Database["public"]["Enums"]["user_role"]
          student_code?: string | null
        }
        Relationships: []
      }
      question_options: {
        Row: {
          id: string
          is_correct: boolean
          option_text: string
          position: number
          question_id: string
        }
        Insert: {
          id?: string
          is_correct?: boolean
          option_text: string
          position: number
          question_id: string
        }
        Update: {
          id?: string
          is_correct?: boolean
          option_text?: string
          position?: number
          question_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "question_options_question_id_fkey"
            columns: ["question_id"]
            isOneToOne: false
            referencedRelation: "questions"
            referencedColumns: ["id"]
          },
        ]
      }
      questions: {
        Row: {
          correct_numeric_answer: number | null
          correct_text_answer: string | null
          created_at: string
          id: string
          numeric_tolerance: number | null
          points: number
          position: number
          question_type: Database["public"]["Enums"]["question_type"]
          session_id: string
          source_format: string | null
          statement: string
        }
        Insert: {
          correct_numeric_answer?: number | null
          correct_text_answer?: string | null
          created_at?: string
          id?: string
          numeric_tolerance?: number | null
          points?: number
          position: number
          question_type: Database["public"]["Enums"]["question_type"]
          session_id: string
          source_format?: string | null
          statement: string
        }
        Update: {
          correct_numeric_answer?: number | null
          correct_text_answer?: string | null
          created_at?: string
          id?: string
          numeric_tolerance?: number | null
          points?: number
          position?: number
          question_type?: Database["public"]["Enums"]["question_type"]
          session_id?: string
          source_format?: string | null
          statement?: string
        }
        Relationships: [
          {
            foreignKeyName: "questions_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "exam_sessions"
            referencedColumns: ["id"]
          },
        ]
      }
      reference_faces: {
        Row: {
          embedding: number[] | null
          model_version: string | null
          registered_at: string
          storage_path: string
          student_id: string
        }
        Insert: {
          embedding?: number[] | null
          model_version?: string | null
          registered_at?: string
          storage_path: string
          student_id: string
        }
        Update: {
          embedding?: number[] | null
          model_version?: string | null
          registered_at?: string
          storage_path?: string
          student_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "reference_faces_student_id_fkey"
            columns: ["student_id"]
            isOneToOne: true
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      risk_scores: {
        Row: {
          breakdown: Json
          computed_at: string
          score: number
          session_id: string
          student_id: string
        }
        Insert: {
          breakdown?: Json
          computed_at?: string
          score: number
          session_id: string
          student_id: string
        }
        Update: {
          breakdown?: Json
          computed_at?: string
          score?: number
          session_id?: string
          student_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "risk_scores_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "exam_sessions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "risk_scores_student_id_fkey"
            columns: ["student_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      session_modules: {
        Row: {
          enabled: boolean
          module: Database["public"]["Enums"]["supervision_module"]
          session_id: string
          settings: Json
        }
        Insert: {
          enabled?: boolean
          module: Database["public"]["Enums"]["supervision_module"]
          session_id: string
          settings?: Json
        }
        Update: {
          enabled?: boolean
          module?: Database["public"]["Enums"]["supervision_module"]
          session_id?: string
          settings?: Json
        }
        Relationships: [
          {
            foreignKeyName: "session_modules_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "exam_sessions"
            referencedColumns: ["id"]
          },
        ]
      }
      session_participants: {
        Row: {
          attempt: number
          consent_at: string | null
          id: string
          requested_in_person: boolean
          score: number | null
          session_id: string
          started_at: string | null
          student_id: string
          submitted_at: string | null
          verification_reviewed_by: string | null
          verification_status: Database["public"]["Enums"]["verification_status"]
          verified_at: string | null
        }
        Insert: {
          attempt?: number
          consent_at?: string | null
          id?: string
          requested_in_person?: boolean
          score?: number | null
          session_id: string
          started_at?: string | null
          student_id: string
          submitted_at?: string | null
          verification_reviewed_by?: string | null
          verification_status?: Database["public"]["Enums"]["verification_status"]
          verified_at?: string | null
        }
        Update: {
          attempt?: number
          consent_at?: string | null
          id?: string
          requested_in_person?: boolean
          score?: number | null
          session_id?: string
          started_at?: string | null
          student_id?: string
          submitted_at?: string | null
          verification_reviewed_by?: string | null
          verification_status?: Database["public"]["Enums"]["verification_status"]
          verified_at?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "session_participants_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "exam_sessions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "session_participants_student_id_fkey"
            columns: ["student_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "session_participants_verification_reviewed_by_fkey"
            columns: ["verification_reviewed_by"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      alert_severity: "low" | "medium" | "high"
      decision_type: "confirmed" | "dismissed" | "retake"
      event_type:
        | "focus_lost"
        | "gaze_away"
        | "face_absent"
        | "extra_person"
        | "extra_display"
        | "suspicious_process"
        | "screen_share"
        | "speech_detected"
        | "identity_check"
      question_type:
        | "multiple_choice"
        | "true_false"
        | "numeric"
        | "fill_blank"
        | "essay"
      session_status: "draft" | "scheduled" | "in_progress" | "finished"
      supervision_module:
        | "face_verification"
        | "face_reverification"
        | "focus_loss"
        | "copy_paste_block"
        | "multi_monitor"
        | "gaze"
        | "extra_person"
        | "objects"
        | "external_voices"
        | "ai_voice"
        | "live_monitoring"
        | "screen_capture"
      supervision_preset: "basic" | "standard" | "strict" | "custom"
      user_role: "teacher" | "student"
      verification_status:
        | "pending"
        | "verified"
        | "failed"
        | "manually_approved"
        | "rejected"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends (DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never) = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends (PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never) = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      alert_severity: ["low", "medium", "high"],
      decision_type: ["confirmed", "dismissed", "retake"],
      event_type: [
        "focus_lost",
        "gaze_away",
        "face_absent",
        "extra_person",
        "extra_display",
        "suspicious_process",
        "screen_share",
        "speech_detected",
        "identity_check",
      ],
      question_type: [
        "multiple_choice",
        "true_false",
        "numeric",
        "fill_blank",
        "essay",
      ],
      session_status: ["draft", "scheduled", "in_progress", "finished"],
      supervision_module: [
        "face_verification",
        "face_reverification",
        "focus_loss",
        "copy_paste_block",
        "multi_monitor",
        "gaze",
        "extra_person",
        "objects",
        "external_voices",
        "ai_voice",
        "live_monitoring",
        "screen_capture",
      ],
      supervision_preset: ["basic", "standard", "strict", "custom"],
      user_role: ["teacher", "student"],
      verification_status: [
        "pending",
        "verified",
        "failed",
        "manually_approved",
        "rejected",
      ],
    },
  },
} as const
