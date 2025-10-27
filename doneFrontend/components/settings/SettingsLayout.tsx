// components/settings/SettingsLayout.tsx
'use client'

import { usePathname } from 'next/navigation'
import Link from 'next/link'
import { User, Shield, Building2, Bell, Smartphone } from 'lucide-react'

const settingsNavItems = [
  {
    href: '/settings/profile',
    label: 'Profile',
    icon: User
  },
  {
    href: '/settings/account',
    label: 'Account',
    icon: Shield
  },
  {
    href: '/settings/school',
    label: 'School',
    icon: Building2
  },
  {
    href: '/settings/devices&messaging',
    label: 'Devices & Messaging',
    icon: Smartphone
  },
  {
    href: '/settings/notifications',
    label: 'Notifications',
    icon: Bell
  }
]

interface SettingsLayoutProps {
  children: React.ReactNode
  title?: string
  subtitle?: string
}

export default function SettingsLayout({ 
  children, 
  title = "Settings",
  subtitle = "Manage your account and preferences"
}: SettingsLayoutProps) {
  const pathname = usePathname()

  return (
    <div className="min-h-screen bg-neutral-50 dark:bg-neutral-950">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
            {title}
          </h1>
          <p className="text-neutral-600 dark:text-neutral-400 mt-2">
            {subtitle}
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8 h-[calc(100vh-200px)]">
          {/* Sidebar Navigation */}
          <div className="lg:col-span-1">
            <nav className="space-y-1 sticky top-8">
              {settingsNavItems.map((item) => {
                const Icon = item.icon
                const isActive = pathname === item.href
                
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`
                      flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
                      ${isActive
                        ? 'bg-neutral-200 dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100'
                        : 'text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800 hover:text-neutral-900 dark:hover:text-neutral-100'
                      }
                    `}
                  >
                    <Icon size={18} className="flex-shrink-0" />
                    <span>{item.label}</span>
                  </Link>
                )
              })}
            </nav>
          </div>

          {/* Content Area - Now Scrollable */}
          <div className="lg:col-span-3 h-full overflow-hidden">
            <div className="card h-full overflow-y-auto">
              <div className="p-6">
                {children}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}