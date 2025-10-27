// services/schools.ts
import { api } from './api'

type CreateSchoolRequest = {
  name: string
  short_code?: string
  email?: string
  phone?: string
  address?: string
  currency?: string
  academic_year_start?: string
  boarding_type?: 'DAY' | 'BOARDING' | 'BOTH'
  gender_type?: 'BOYS' | 'GIRLS' | 'MIXED'
}

type UpdateSchoolRequest = {
  name?: string
  short_code?: string
  email?: string
  phone?: string
  address?: string
  currency?: string
  academic_year_start?: string
  boarding_type?: 'DAY' | 'BOARDING' | 'BOTH'
  gender_type?: 'BOYS' | 'GIRLS' | 'MIXED'
}

export type School = {
  id: string
  name: string
  short_code?: string
  email?: string
  phone?: string
  address?: string
  currency?: string
  academic_year_start?: string
  boarding_type?: 'DAY' | 'BOARDING' | 'BOTH'
  gender_type?: 'BOYS' | 'GIRLS' | 'MIXED'
  owner_user_id: string
}

export type SchoolLite = {
  id: string
  name: string
}

export type SchoolOverview = {
  students: number
  classes: number
  feesCollected: number
  pendingInvoices: number
}

export type SchoolMineItem = {
  id: string
  name: string
  role: string
}

// Mobile Device Types
export type MobileDeviceStatus = {
  device_id: string
  app_version?: string
  device_model?: string
  android_version?: string
  
  notification_access: boolean
  sms_permission: boolean
  listener_connected: boolean
  last_forward_ok: boolean
  last_error?: string
  
  network_status?: string
  battery_optimized?: boolean
  last_sms_received_at?: string
  
  first_seen_at: string
  last_update_at: string
  last_heartbeat_at: string
  
  // Computed properties
  is_online: boolean
  is_healthy: boolean
  status_summary: 'connected' | 'issues' | 'offline'
}

export type MobileDeviceListResponse = {
  devices: MobileDeviceStatus[]
  total_count: number
  connected_count: number
  healthy_count: number
}

export const schoolService = {
  async mine() {
    const { data } = await api.get('/api/schools/mine')
    return data as SchoolMineItem[]
  },

  async getActive() {
    const { data } = await api.get('/api/schools/active')
    return data as SchoolLite
  },
  
  async create(body: CreateSchoolRequest) {
    const { data } = await api.post('/api/schools', body)
    return data as School
  },
  
  async get(id: string) {
    const { data } = await api.get(`/api/schools/${id}`, {
      headers: {
        'X-School-ID': id
      }
    })
    return data as School
  },

  async getOverview(schoolId: string) {
    const { data } = await api.get('/api/schools/overview', {
      headers: {
        'X-School-ID': schoolId
      }
    })
    return data as SchoolOverview
  },
  
  async update(id: string, body: UpdateSchoolRequest) {
    const { data } = await api.put(`/api/schools/${id}`, body, {
      headers: {
        'X-School-ID': id
      }
    })
    return data as School
  },

  // Mobile Device Status Methods
  async getMobileDevices(schoolId: string) {
    const { data } = await api.get('/api/mobile/status', {
      headers: {
        'X-School-ID': schoolId
      }
    })
    return data as MobileDeviceListResponse
  },

  async removeMobileDevice(schoolId: string, deviceId: string) {
    const { data } = await api.delete(`/api/mobile/status/${deviceId}`, {
      headers: {
        'X-School-ID': schoolId
      }
    })
    return data as { success: boolean; message: string }
  },

  async getAllSchoolDevices(schoolId: string) {
    const { data } = await api.get('/api/mobile/debug/all-devices', {
      headers: {
        'X-School-ID': schoolId
      }
    })
    return data as {
      school_id: string
      total_devices: number
      devices: Array<{
        device_id: string
        user_id: string
        app_version?: string
        device_model?: string
        status_summary: string
        is_online: boolean
        is_healthy: boolean
        last_heartbeat_at?: string
        last_sms_received_at?: string
        last_error?: string
      }>
      summary: {
        online: number
        healthy: number
        with_errors: number
      }
    }
  }
}

// Export individual functions for convenience
export const createSchool = schoolService.create
export const getSchool = schoolService.get
export const getSchoolOverview = schoolService.getOverview
export const updateSchool = schoolService.update
export const getMobileDevices = schoolService.getMobileDevices
export const removeMobileDevice = schoolService.removeMobileDevice
export const getAllSchoolDevices = schoolService.getAllSchoolDevices