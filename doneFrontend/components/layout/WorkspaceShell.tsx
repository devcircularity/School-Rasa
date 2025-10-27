'use client'

import React, { useEffect, useMemo, useRef, useState } from 'react'
import Sidebar from './WorkspaceSidebar'
import CanvasPanel from './WorkspaceCanvas'
import HeaderBar from './HeaderBar'
import AcademicStatusBar from './AcademicStatusBar' // Add this import


// Simple event bus so any page/component can open the canvas
type CanvasCommand = { type: 'open' | 'close' | 'toggle', width?: number }
type Listener = (cmd: CanvasCommand) => void

const listeners = new Set<Listener>()
export const CanvasBus = {
  send(cmd: CanvasCommand) { listeners.forEach(l => l(cmd)) },
  on(l: Listener) { 
    listeners.add(l); 
    return () => { 
      listeners.delete(l) 
    } 
  }
}

// Sidebar toggle bus for header integration and auto-collapse
type SidebarCommand = { type: 'toggle' | 'open' | 'close' | 'auto-collapse' }
type SidebarListener = (cmd: SidebarCommand) => void

const sidebarListeners = new Set<SidebarListener>()
export const SidebarBus = {
  send(cmd: SidebarCommand) { sidebarListeners.forEach(l => l(cmd)) },
  on(l: SidebarListener) { 
    sidebarListeners.add(l); 
    return () => { 
      sidebarListeners.delete(l) 
    } 
  }
}

export default function WorkspaceShell({ children }: { children: React.ReactNode }) {
  // Sidebar collapsed state (persist) - responsive defaults
  const [collapsed, setCollapsed] = useState<boolean>(true)
  const [isMobile, setIsMobile] = useState(false)
  
  // Check mobile screen size
  useEffect(() => {
    const checkMobile = () => {
      const mobile = window.innerWidth < 1024 // lg breakpoint
      setIsMobile(mobile)
      
      // Auto-collapse on mobile, restore on desktop
      if (mobile) {
        setCollapsed(true)
      }
    }
    
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])
  
  useEffect(() => {
    const saved = localStorage.getItem('sidebar_collapsed')
    // Always default to collapsed, but respect saved preference if user has explicitly expanded it
    if (saved === '0' && !isMobile) {
      // Only expand if user previously chose to expand (saved as '0')
      setCollapsed(false)
    }
    // If no saved preference or saved as '1', keep collapsed (which is already the default)
  }, [isMobile])
  
  const toggleSidebar = (newState?: boolean) => {
    console.log('Toggle sidebar called:', { newState, currentCollapsed: collapsed, isMobile })
    setCollapsed(prev => {
      const next = newState !== undefined ? newState : !prev
      console.log('Sidebar state changing from', prev, 'to', next)
      // Only persist on desktop
      if (!isMobile) {
        localStorage.setItem('sidebar_collapsed', next ? '1' : '0')
      }
      return next
    })
  }

  // Listen for sidebar toggle commands from header and auto-collapse
  useEffect(() => {
    const unsubscribe = SidebarBus.on((cmd) => {
      console.log('SidebarBus command received:', cmd, { isMobile, collapsed })
      if (cmd.type === 'toggle') toggleSidebar()
      if (cmd.type === 'open') toggleSidebar(false)
      if (cmd.type === 'close') toggleSidebar(true)
      if (cmd.type === 'auto-collapse' && !isMobile && !collapsed) {
        // Auto-collapse only on desktop when sidebar is expanded
        console.log('Auto-collapsing sidebar after user action')
        toggleSidebar(true)
      }
    })
    
    return unsubscribe
  }, [toggleSidebar, isMobile, collapsed])

  // Canvas open/width state (persist). Closed by default, disabled on mobile
  const [canvasOpen, setCanvasOpen] = useState<boolean>(false)
  const [canvasWidth, setCanvasWidth] = useState<number>(420)
  
  useEffect(() => {
    // Canvas is desktop-only
    if (isMobile) {
      setCanvasOpen(false)
      return
    }
    
    const open = localStorage.getItem('canvas_open')
    const w = localStorage.getItem('canvas_width')
    if (open) setCanvasOpen(open === '1')
    if (w) setCanvasWidth(Math.max(320, Math.min(800, parseInt(w, 10) || 420)))
    
    const unsubscribe = CanvasBus.on((cmd) => {
      if (isMobile) return // Ignore canvas commands on mobile
      
      if (cmd.type === 'open') setCanvasOpen(true)
      if (cmd.type === 'close') setCanvasOpen(false)
      if (cmd.type === 'toggle') setCanvasOpen(o => !o)
      if (cmd.width) setCanvasWidth(Math.max(320, Math.min(800, cmd.width)))
    })
    
    return unsubscribe
  }, [isMobile])
  
  useEffect(() => { 
    if (!isMobile) {
      localStorage.setItem('canvas_open', canvasOpen ? '1' : '0') 
    }
  }, [canvasOpen, isMobile])
  
  useEffect(() => { 
    if (!isMobile) {
      localStorage.setItem('canvas_width', String(canvasWidth)) 
    }
  }, [canvasWidth, isMobile])

  // Mobile overlay backdrop when sidebar is open
  const showMobileOverlay = isMobile && !collapsed

  return (
    <div className="h-svh w-full overflow-hidden">
      <div className="flex-1 overflow-hidden relative h-full">
        {/* Mobile overlay backdrop */}
        {isMobile && !collapsed && (
          <div 
            className="fixed inset-0 bg-black/50 z-30"
            onClick={() => toggleSidebar(true)}
          />
        )}
        
        {/* Content row: sidebar | main | canvas - CRITICAL: Fixed height flow */}
        <div className="relative flex overflow-hidden h-full">
          {/* Sidebar - Always visible on desktop, overlay on mobile */}
          <div className={`
            transition-all duration-300 ease-in-out
            ${isMobile 
              ? `fixed left-0 top-0 h-full w-80 z-40 ${collapsed ? '-translate-x-full' : 'translate-x-0'}` 
              : `relative z-10 ${collapsed ? 'w-16' : 'w-auto'}`
            }
          `}>
            <Sidebar 
              collapsed={collapsed && !isMobile}
              onCollapse={toggleSidebar} 
              isMobile={isMobile}
            />
          </div>

          {/* Main content area with header - CRITICAL: Fixed flex layout */}
          <div className="flex-1 min-w-0 flex flex-col h-full overflow-hidden">
            {/* Header Bar */}
            <div className="flex-shrink-0">
              <HeaderBar />
            </div>
            
            {/* Academic Status Bar - ADD THIS HERE */}
            <div className="flex-shrink-0">
              <AcademicStatusBar />
            </div>
            
            {/* Main Content - CRITICAL: This div must have proper height constraints */}
            <div className="flex-1 min-h-0 overflow-hidden">
              {children}
            </div>
          </div>

          {/* Canvas (desktop-only, retractable, resizable) */}
          {!isMobile && (
            <CanvasPanel
              open={canvasOpen}
              width={canvasWidth}
              onResize={setCanvasWidth}
              onRequestClose={() => setCanvasOpen(false)}
            />
          )}
        </div>
      </div>
    </div>
  )
}