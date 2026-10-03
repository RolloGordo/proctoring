export {}

declare global {
  interface Window {
    api: {
      listEvents: () => Promise<ProctoringEvent[]>
      setAuthSession: (session: AuthSession | null) => Promise<void>
      /** Devuelve una funcion para dejar de escuchar */
      onNewEvent: (callback: (event: ProctoringEvent) => void) => () => void
      getDisplayCount: () => Promise<number>
      onDisplayCountChange: (callback: (count: number) => void) => () => void
    }
  }
}
