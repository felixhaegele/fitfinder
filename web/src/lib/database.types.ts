
export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[]

export type Database = {
  
  "graphql_public": {
          Tables: {
            [_ in never]: never
          }
          Views: {
            [_ in never]: never
          }
          Functions: {
            "graphql":
{ Args: { "extensions"?: Json,"operationName"?: string,"query"?: string,"variables"?: Json }; Returns: Json
                           }
          }
          Enums: {
            [_ in never]: never
          }
          CompositeTypes: {
            [_ in never]: never
          }
        },"public": {
          Tables: {
            "classifications": {
                  Row: {
                    "arch_class": string,"classifier_version": string,"created_at": string,"id": string,"measurement_id": string,"toe_box_shape": string,"width_class": string
                  }
                  ComputedFields: never
                  Insert: {
                    "arch_class": string,"classifier_version": string,"created_at"?: string,"id"?: string,"measurement_id": string,"toe_box_shape": string,"width_class": string
                  }
                  Update: {
                    "arch_class"?: string,"classifier_version"?: string,"created_at"?: string,"id"?: string,"measurement_id"?: string,"toe_box_shape"?: string,"width_class"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "classifications_measurement_id_fkey"
      columns: ["measurement_id"]
isOneToOne: false
      referencedRelation: "measurements"
      referencedColumns: ["id"]
    }
                  ]
                },"measurements": {
                  Row: {
                    "arch_width_mm": number,"ball_width_mm": number,"created_at": string,"extra": NonNullable<Json>,"heel_width_mm": number,"id": string,"length_mm": number,"pipeline_version": string,"submission_id": string,"toe_taper": number | null
                  }
                  ComputedFields: never
                  Insert: {
                    "arch_width_mm": number,"ball_width_mm": number,"created_at"?: string,"extra"?: NonNullable<Json>,"heel_width_mm": number,"id"?: string,"length_mm": number,"pipeline_version": string,"submission_id": string,"toe_taper"?: number | null
                  }
                  Update: {
                    "arch_width_mm"?: number,"ball_width_mm"?: number,"created_at"?: string,"extra"?: NonNullable<Json>,"heel_width_mm"?: number,"id"?: string,"length_mm"?: number,"pipeline_version"?: string,"submission_id"?: string,"toe_taper"?: number | null
                  }
                  Relationships: [
                    {
      foreignKeyName: "measurements_submission_id_fkey"
      columns: ["submission_id"]
isOneToOne: false
      referencedRelation: "submissions"
      referencedColumns: ["id"]
    }
                  ]
                },"profiles": {
                  Row: {
                    "created_at": string,"id": string
                  }
                  ComputedFields: never
                  Insert: {
                    "created_at"?: string,"id": string
                  }
                  Update: {
                    "created_at"?: string,"id"?: string
                  }
                  Relationships: [
                    
                  ]
                },"shoe_models": {
                  Row: {
                    "brand": string,"created_at": string,"created_by": string | null,"id": string,"model": string,"year": number
                  }
                  ComputedFields: never
                  Insert: {
                    "brand": string,"created_at"?: string,"created_by"?: string | null,"id"?: string,"model": string,"year": number
                  }
                  Update: {
                    "brand"?: string,"created_at"?: string,"created_by"?: string | null,"id"?: string,"model"?: string,"year"?: number
                  }
                  Relationships: [
                    {
      foreignKeyName: "shoe_models_created_by_fkey"
      columns: ["created_by"]
isOneToOne: false
      referencedRelation: "profiles"
      referencedColumns: ["id"]
    }
                  ]
                },"submissions": {
                  Row: {
                    "consent_at": string,"created_at": string,"id": string,"image_path": string,"insole_condition": string,"processed_image_path": string | null,"rejection_reason": string | null,"shoe_model_id": string,"size": number,"size_system": string,"status": string,"updated_at": string,"user_id": string
                  }
                  ComputedFields: never
                  Insert: {
                    "consent_at": string,"created_at"?: string,"id"?: string,"image_path": string,"insole_condition": string,"processed_image_path"?: string | null,"rejection_reason"?: string | null,"shoe_model_id": string,"size": number,"size_system": string,"status"?: string,"updated_at"?: string,"user_id"?: string
                  }
                  Update: {
                    "consent_at"?: string,"created_at"?: string,"id"?: string,"image_path"?: string,"insole_condition"?: string,"processed_image_path"?: string | null,"rejection_reason"?: string | null,"shoe_model_id"?: string,"size"?: number,"size_system"?: string,"status"?: string,"updated_at"?: string,"user_id"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "submissions_shoe_model_id_fkey"
      columns: ["shoe_model_id"]
isOneToOne: false
      referencedRelation: "shoe_models"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "submissions_user_id_fkey"
      columns: ["user_id"]
isOneToOne: false
      referencedRelation: "profiles"
      referencedColumns: ["id"]
    }
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
            [_ in never]: never
          }
          CompositeTypes: {
            [_ in never]: never
          }
        }
}

type DatabaseWithoutInternals = Omit<Database, '__InternalSupabase'>

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never
> = DefaultSchemaTableNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
  ? (DefaultSchema["Tables"] & DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
      Row: infer R
    }
    ? R
    : never
  : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never
> = DefaultSchemaTableNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
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
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never
> = DefaultSchemaTableNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
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
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never
> = DefaultSchemaEnumNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
  ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
  : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never
> = PublicCompositeTypeNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
  ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
  : never

export const Constants = {
  "graphql_public": {
          Enums: {
            
          }
        },"public": {
          Enums: {
            
          }
        }
} as const
