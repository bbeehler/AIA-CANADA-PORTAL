export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[];

type ProfileRow = {
  id: string;
  email: string;
  full_name: string;
  organization: string;
  province: string;
  role: string;
  membership_status: string;
  created_at: string;
  updated_at: string;
};

type ContributionRow = {
  id: string;
  contributor_id: string;
  storage_path: string;
};

type AuditLogRow = {
  id: number;
  actor_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  details: Json;
  created_at: string;
};

export type Database = {
  public: {
    Tables: {
      profiles: {
        Row: ProfileRow;
        Insert: Partial<ProfileRow> & { id: string };
        Update: Partial<ProfileRow>;
        Relationships: [];
      };
      contributions: {
        Row: ContributionRow;
        Insert: Partial<ContributionRow> & {
          contributor_id: string;
          storage_path: string;
        };
        Update: Partial<ContributionRow>;
        Relationships: [];
      };
      audit_log: {
        Row: AuditLogRow;
        Insert: Omit<AuditLogRow, "id" | "created_at"> & {
          id?: number;
          created_at?: string;
        };
        Update: Partial<AuditLogRow>;
        Relationships: [];
      };
    };
    Views: Record<string, never>;
    Functions: Record<string, never>;
    Enums: Record<string, never>;
    CompositeTypes: Record<string, never>;
  };
};
