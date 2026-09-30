export const studyPlanKeys = {
  all: ['study-plan'] as const,
  drafts: () => ['study-plan', 'draft'] as const,
  draft: (id: string) => ['study-plan', 'draft', id] as const,
  export: (id: string) => ['study-plan', 'export', id] as const,
}
