// components/layout/HeaderBar.tsx - With academic info badges
'use client'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import Link from 'next/link'
import { Menu, GraduationCap, Users } from 'lucide-react'
import UserControlsModal from './UserControlsModal'
import { SidebarBus } from './WorkspaceShell'
import { academicStatusService, type AcademicStatus } from '@/services/academic-status'

// Header title bus for dynamic title updates
type HeaderTitleCommand = { type: 'set', title: string, subtitle?: string } | { type: 'clear' }
type HeaderTitleListener = (cmd: HeaderTitleCommand) => void

const headerTitleListeners = new Set<HeaderTitleListener>()
export const HeaderTitleBus = {
  send(cmd: HeaderTitleCommand) { headerTitleListeners.forEach(l => l(cmd)) },
  on(l: HeaderTitleListener) { 
    headerTitleListeners.add(l); 
    return () => { 
      headerTitleListeners.delete(l) 
    } 
  }
}

function decodeJwt(token?: string) {
  if (!token) return null
  try {
    const base = token.split('.')[1]?.replace(/-/g, '+').replace(/_/g, '/')
    const json = atob(base)
    return JSON.parse(json) as { email?: string; full_name?: string; active_school_id?: number | string }
  } catch { return null }
}

function initialsFrom(name?: string, email?: string) {
  const n = (name || '').trim()
  if (n) {
    const parts = n.split(/\s+/).slice(0,2)
    return parts.map(p => p[0]?.toUpperCase() || '').join('') || 'U'
  }
  if (email) return email[0]?.toUpperCase() || 'U'
  return 'U'
}

export default function HeaderBar() {
  const { token, active_school_id, logout } = useAuth()
  const [openModal, setOpenModal] = useState(false)
  const [showTip, setShowTip] = useState(false)
  const [isMobile, setIsMobile] = useState(false)
  const [pageTitle, setPageTitle] = useState<string>('')
  const [pageSubtitle, setPageSubtitle] = useState<string>('')
  const [academicStatus, setAcademicStatus] = useState<AcademicStatus | null>(null)
  const [classCount, setClassCount] = useState<number>(0)
  const tipRef = useRef<HTMLDivElement>(null)
  const refreshTimeoutRef = useRef<NodeJS.Timeout>()

  const claims = useMemo(() => decodeJwt(token || undefined), [token])
  const name = claims?.full_name
  const email = claims?.email
  const userLabel = name || email || 'Guest'
  const avatarTxt = initialsFrom(name, email)
  const schoolId = active_school_id ?? claims?.active_school_id

  // Check mobile screen size
  useEffect(() => {
    const checkMobile = () => {
      const mobile = window.innerWidth < 1024 // lg breakpoint
      setIsMobile(mobile)
    }
    
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])

  // Load academic status and class count
  useEffect(() => {
    if (!token) return
    
    loadAcademicInfo()
    
    // Refresh every 5 minutes
    const interval = setInterval(loadAcademicInfo, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [token])

  // Listen for academic status updates with debouncing
  useEffect(() => {
    const handleStatusUpdate = () => {
      if (refreshTimeoutRef.current) {
        clearTimeout(refreshTimeoutRef.current)
      }
      
      refreshTimeoutRef.current = setTimeout(() => {
        loadAcademicInfo()
      }, 500)
    }

    window.addEventListener('academic-status-updated', handleStatusUpdate)
    
    return () => {
      window.removeEventListener('academic-status-updated', handleStatusUpdate)
      if (refreshTimeoutRef.current) {
        clearTimeout(refreshTimeoutRef.current)
      }
    }
  }, [])

  async function loadAcademicInfo() {
    try {
      // Load academic status
      const status = await academicStatusService.getStatus()
      setAcademicStatus(status)

      // Load class count
      const response = await fetch('/api/classes?limit=1', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-School-ID': schoolId as string
        }
      })

      if (response.ok) {
        const data = await response.json()
        setClassCount(data.total || 0)
      }
    } catch (error) {
      console.error('Failed to load academic info:', error)
    }
  }

  // Listen for header title updates
  useEffect(() => {
    const unsubscribe = HeaderTitleBus.on((cmd) => {
      if (cmd.type === 'set') {
        setPageTitle(cmd.title)
        setPageSubtitle(cmd.subtitle || '')
      } else if (cmd.type === 'clear') {
        setPageTitle('')
        setPageSubtitle('')
      }
    })
    
    return unsubscribe
  }, [])

  // Hover tooltip hide on outside click
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (!tipRef.current) return
      if (!tipRef.current.contains(e.target as Node)) setShowTip(false)
    }
    document.addEventListener('click', onClick)
    return () => document.removeEventListener('click', onClick)
  }, [])

  const handleSidebarToggle = () => {
    SidebarBus.send({ type: 'toggle' })
  }

  const showAcademicBadges = token && academicStatus?.setup_complete

  return (
    <header className="flex items-center justify-between px-4 py-3 border-b border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900">
      {/* Left side - Hamburger menu and title */}
      <div className="flex items-center gap-3 min-w-0 flex-1">
        {isMobile && (
          <button
            onClick={handleSidebarToggle}
            className="p-2 -ml-2 rounded-md hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
            aria-label="Toggle sidebar"
          >
            <Menu size={20} className="text-neutral-600 dark:text-neutral-400" />
          </button>
        )}
        
        {/* Dynamic page title */}
        {pageTitle && (
          <div className="min-w-0 flex-1">
            <h1 className="text-base sm:text-lg font-semibold text-neutral-900 dark:text-neutral-100 truncate">
              {pageTitle}
            </h1>
            {pageSubtitle && (
              <p className="text-xs sm:text-sm text-neutral-600 dark:text-neutral-400 truncate">
                {pageSubtitle}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Center - Academic Info Badges (only when setup complete) */}
      {showAcademicBadges && (
        <div className="hidden lg:flex items-center gap-2 px-4 text-xs">
          {/* Academic Year Badge */}
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-neutral-100 dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700">
            <GraduationCap className="w-3.5 h-3.5 text-neutral-600 dark:text-neutral-400" />
            <span className="font-medium text-neutral-900 dark:text-neutral-100">
              {academicStatus.academic_year?.year || 'No Year'}
            </span>
          </div>

          {/* Divider */}
          <div className="h-4 w-px bg-neutral-300 dark:bg-neutral-700" />

          {/* Term Info */}
          <div className="flex items-center gap-1.5 text-neutral-600 dark:text-neutral-400">
            <span>Term</span>
            <span className="font-semibold text-neutral-900 dark:text-neutral-100">
              {academicStatus.active_term?.term || '-'}
            </span>
          </div>

          {/* Divider */}
          <div className="h-4 w-px bg-neutral-300 dark:bg-neutral-700" />

          {/* Classes Badge */}
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-neutral-100 dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700">
            <Users className="w-3.5 h-3.5 text-neutral-600 dark:text-neutral-400" />
            <span className="font-medium text-neutral-900 dark:text-neutral-100">
              {classCount}
            </span>
            <span className="hidden xl:inline text-neutral-600 dark:text-neutral-400">
              {classCount === 1 ? 'Class' : 'Classes'}
            </span>
          </div>
        </div>
      )}


    </header>
  )
}