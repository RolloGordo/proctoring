export {}

declare global {
  interface Window {
    api: {
      listEvents: () => Promise<ProctoringEvent[]>
      setAuthSession: (session: AuthSession | null) => Promise<void>
      /** Devuelve una funcion para dejar de escuchar */
      onNewEvent: (callback: (event: ProctoringEvent) => void) => () => void
      getDisplayCount: () => Promise<number>
      getExamContext: () => Promise<{ session_id: string; student_id: string }>
      onDisplayCountChange: (callback: (count: number) => void) => () => void
    }
  }
}
