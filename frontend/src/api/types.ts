// Friendly application names for generated wire contracts. Do not redefine payloads here.
export type {
  ConfigOut as AppConfig,
  CitationOut as Citation,
  ResearchResultOut as ResearchResult,
  RunOut as Run,
  ConversationOut as Conversation,
  ConversationDetailOut as ConversationDetail,
  MessageOut as ConversationMessage,
  ResearchProgressEvent as ProgressEvent,
  ResearchEventOut as ResearchEvent,
  UploadEventOut as UploadEvent,
  DraftOut as Draft,
  PageOut as NotionPage,
  ExportOut as ExportResult,
  NotionStatusOut as NotionStatus,
} from './contracts/generated/types.gen'
import type { ConfigOut, NotionStatusOut, RunOut } from './contracts/generated/types.gen'
export type NotionBackend = ConfigOut['notion_backend']
export type ConnectionState = NotionStatusOut['status']
export type RunStatus = RunOut['status']
