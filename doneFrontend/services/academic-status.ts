// services/academic-status.ts
import { api } from './api'

export interface AcademicStatus {
  academic_year: {
    id: string
    name: string
    year: number
    start_date: string
    end_date: string
    state: string
  } | null
  active_term: {
    id: string
    name: string
    term: number
    start_date: string
    end_date: string
    state: string
  } | null
  has_classes: boolean
  setup_complete: boolean
  warnings: string[]
}

export const academicStatusService = {
  async getStatus(): Promise<AcademicStatus> {
    const response = await api.get('/api/academic/status')  // Fixed: added /api prefix
    return response.data
  }
}