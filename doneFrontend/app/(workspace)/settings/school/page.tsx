// app/settings/school/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import SettingsLayout from '@/components/settings/SettingsLayout'
import { schoolService, School } from '@/services/schools'
import { Building2, Calendar, DollarSign, Users } from 'lucide-react'

export default function SchoolSettings() {
  const { active_school_id, isAuthenticated } = useAuth()
  const [school, setSchool] = useState<School | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [shortCodeManuallyEdited, setShortCodeManuallyEdited] = useState(false)

  const [form, setForm] = useState({
    name: '',
    short_code: '',
    email: '',
    phone: '',
    address: '',
    currency: 'KES',
    academic_year_start: '',
    boarding_type: '' as '' | 'DAY' | 'BOARDING' | 'BOTH',
    gender_type: '' as '' | 'BOYS' | 'GIRLS' | 'MIXED',
  })

  // Load school data
  useEffect(() => {
    const loadSchool = async () => {
      if (!isAuthenticated || !active_school_id) {
        setLoading(false)
        return
      }

      try {
        setLoading(true)
        const currentSchool = await schoolService.get(active_school_id)
        
        if (currentSchool) {
          setSchool(currentSchool)
          setForm({
            name: currentSchool.name || '',
            short_code: currentSchool.short_code || '',
            email: currentSchool.email || '',
            phone: currentSchool.phone || '',
            address: currentSchool.address || '',
            currency: currentSchool.currency || 'KES',
            academic_year_start: currentSchool.academic_year_start || '',
            boarding_type: currentSchool.boarding_type || '',
            gender_type: currentSchool.gender_type || '',
          })
          setShortCodeManuallyEdited(!!currentSchool.short_code)
        }
      } catch (err: any) {
        console.error('Failed to load school:', err)
        setError(err?.response?.data?.detail || 'Failed to load school information')
      } finally {
        setLoading(false)
      }
    }

    loadSchool()
  }, [isAuthenticated, active_school_id])

  // Generate short code from school name
  function generateShortCode(schoolName: string): string {
    return schoolName
      .split(/\s+/)
      .filter(word => word.length > 0)
      .map(word => word[0])
      .join('')
      .toUpperCase()
      .slice(0, 10)
  }

  const handleSave = async () => {
    if (!active_school_id) return

    setError(null)
    setSaving(true)

    try {
      await schoolService.update(active_school_id, {
        name: form.name.trim() || undefined,
        short_code: form.short_code || undefined,
        email: form.email || undefined,
        phone: form.phone || undefined,
        address: form.address || undefined,
        currency: form.currency || undefined,
        academic_year_start: form.academic_year_start || undefined,
        boarding_type: form.boarding_type || undefined,
        gender_type: form.gender_type || undefined,
      })

      setSaved(true)
      setTimeout(() => setSaved(false), 3000)

      // Reload school data
      const updatedSchool = await schoolService.get(active_school_id)
      if (updatedSchool) {
        setSchool(updatedSchool)
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to update school settings')
    } finally {
      setSaving(false)
    }
  }

  if (!isAuthenticated) {
    return (
      <SettingsLayout>
        <div className="text-center py-8">
          <p className="text-neutral-600 dark:text-neutral-400">
            Please log in to access school settings.
          </p>
        </div>
      </SettingsLayout>
    )
  }

  if (!active_school_id) {
    return (
      <SettingsLayout>
        <div className="text-center py-8">
          <p className="text-neutral-600 dark:text-neutral-400">
            No active school selected. Please select a school first.
          </p>
        </div>
      </SettingsLayout>
    )
  }

  if (loading) {
    return (
      <SettingsLayout>
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-2 text-sm text-neutral-600 dark:text-neutral-400">Loading school settings...</p>
        </div>
      </SettingsLayout>
    )
  }

  return (
    <SettingsLayout>
      <div className="space-y-8">
        <div>
          <h2 className="text-xl font-semibold text-neutral-900 dark:text-neutral-100 mb-2">
            School Settings
          </h2>
          <p className="text-neutral-600 dark:text-neutral-400">
            Manage your school's basic information and preferences
          </p>
        </div>

        {/* Basic Information */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 mb-4">
            <Building2 className="text-blue-600" size={20} />
            <h3 className="text-lg font-medium text-neutral-900 dark:text-neutral-100">
              Basic Information
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">School name *</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => {
                  const newName = e.target.value
                  setForm({
                    ...form,
                    name: newName,
                    short_code: shortCodeManuallyEdited ? form.short_code : generateShortCode(newName)
                  })
                }}
                className="input"
                placeholder="e.g., Imara Primary School"
                required
              />
            </div>

            <div>
              <label className="label">Short code</label>
              <input
                type="text"
                value={form.short_code}
                onChange={(e) => {
                  setShortCodeManuallyEdited(true)
                  setForm({ ...form, short_code: e.target.value.toUpperCase() })
                }}
                className="input"
                placeholder="IMARA"
                maxLength={10}
              />
              <p className="text-xs text-neutral-500 mt-1">Used for reports and student IDs</p>
            </div>
          </div>
        </div>

        {/* Contact Information */}
        <div className="space-y-4 border-t border-neutral-200 dark:border-neutral-700 pt-8">
          <h3 className="text-lg font-medium text-neutral-900 dark:text-neutral-100 mb-4">
            Contact Information
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Official email</label>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="input"
                placeholder="admin@school.ke"
              />
            </div>

            <div>
              <label className="label">Phone</label>
              <input
                type="tel"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                className="input"
                placeholder="+254..."
              />
            </div>

            <div className="md:col-span-2">
              <label className="label">Address</label>
              <input
                type="text"
                value={form.address}
                onChange={(e) => setForm({ ...form, address: e.target.value })}
                className="input"
                placeholder="School address / Location"
              />
            </div>
          </div>
        </div>

        {/* School Type & Demographics */}
        <div className="space-y-4 border-t border-neutral-200 dark:border-neutral-700 pt-8">
          <div className="flex items-center gap-2 mb-4">
            <Users className="text-blue-600" size={20} />
            <h3 className="text-lg font-medium text-neutral-900 dark:text-neutral-100">
              School Type & Demographics
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">School type *</label>
              <select
                value={form.boarding_type}
                onChange={(e) => setForm({ ...form, boarding_type: e.target.value as any })}
                className="input"
                required
              >
                <option value="" disabled>Select school type</option>
                <option value="DAY">Day school</option>
                <option value="BOARDING">Boarding school</option>
                <option value="BOTH">Day & Boarding</option>
              </select>
            </div>

            <div>
              <label className="label">Gender *</label>
              <select
                value={form.gender_type}
                onChange={(e) => setForm({ ...form, gender_type: e.target.value as any })}
                className="input"
                required
              >
                <option value="" disabled>Select gender type</option>
                <option value="MIXED">Mixed (Boys & Girls)</option>
                <option value="BOYS">Boys only</option>
                <option value="GIRLS">Girls only</option>
              </select>
            </div>
          </div>
        </div>

        {/* Financial & Academic Settings */}
        <div className="space-y-4 border-t border-neutral-200 dark:border-neutral-700 pt-8">
          <div className="flex items-center gap-2 mb-4">
            <DollarSign className="text-blue-600" size={20} />
            <h3 className="text-lg font-medium text-neutral-900 dark:text-neutral-100">
              Financial & Academic Settings
            </h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Currency</label>
              <select
                value={form.currency}
                onChange={(e) => setForm({ ...form, currency: e.target.value })}
                className="input"
              >
                <option value="KES">KES - Kenyan Shilling</option>
                <option value="USD">USD - US Dollar</option>
                <option value="UGX">UGX - Ugandan Shilling</option>
                <option value="TZS">TZS - Tanzanian Shilling</option>
              </select>
            </div>

            <div>
              <label className="label">Academic year start date *</label>
              <input
                type="date"
                value={form.academic_year_start}
                onChange={(e) => setForm({ ...form, academic_year_start: e.target.value })}
                className="input"
                required
              />
              <p className="text-xs text-neutral-500 mt-1">
                Most Kenyan schools start in January
              </p>
            </div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-4">
            <p className="text-red-800 dark:text-red-200 text-sm">{error}</p>
          </div>
        )}

        {/* Save Button */}
        <div className="flex items-center gap-4 pt-4 border-t border-neutral-200 dark:border-neutral-700">
          <button
            onClick={handleSave}
            disabled={saving || !form.name.trim() || !form.boarding_type || !form.gender_type || !form.academic_year_start}
            className="btn-primary"
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>

          {saved && (
            <span className="text-green-600 dark:text-green-400 text-sm font-medium">
              School settings saved successfully!
            </span>
          )}
        </div>
      </div>
    </SettingsLayout>
  )
}