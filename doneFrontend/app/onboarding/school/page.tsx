// onboarding-school/page.tsx

"use client";
import { useSearchParams, useRouter } from "next/navigation";
import { useState, Suspense } from "react";
import { createSchool } from "@/services/schools";
import { useAuth } from "@/contexts/AuthContext";

function OnboardingSchoolForm() {
  const router = useRouter();
  const sp = useSearchParams();
  const next = sp.get("next") || "/";

  const { setSchoolId } = useAuth();

  const currentYear = new Date().getFullYear();
  const defaultAcademicStart = `${currentYear}-01-01`;

  const [form, setForm] = useState({
    name: "",
    short_code: "",
    email: "",
    phone: "",
    address: "",
    currency: "KES",
    academic_year_start: defaultAcademicStart,
    boarding_type: "" as "" | "DAY" | "BOARDING" | "BOTH",
    gender_type: "" as "" | "BOYS" | "GIRLS" | "MIXED",
  });
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [shortCodeManuallyEdited, setShortCodeManuallyEdited] = useState(false);

  // Function to generate short code from school name
  function generateShortCode(schoolName: string): string {
    return schoolName
      .split(/\s+/)
      .filter(word => word.length > 0)
      .map(word => word[0])
      .join("")
      .toUpperCase()
      .slice(0, 10);
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    
    if (!form.name.trim()) return setErr("School name is required");
    if (!form.academic_year_start) return setErr("Academic year start date is required");
    
    setLoading(true);
    try {
      const created = await createSchool({
        name: form.name.trim(),
        short_code: form.short_code || undefined,
        email: form.email || undefined,
        phone: form.phone || undefined,
        address: form.address || undefined,
        currency: form.currency || undefined,
        academic_year_start: form.academic_year_start,
        boarding_type: form.boarding_type || undefined,
        gender_type: form.gender_type || undefined,
      });
      setSchoolId(created.id.toString());
      router.push(next);
    } catch (e: any) {
      setErr(e?.response?.data?.detail || "Failed to create school");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen grid place-items-center p-6">
      <div className="w-full max-w-2xl card p-6 space-y-6">
        <div>
          <h1 className="text-xl font-semibold">Create your school</h1>
          <p className="text-sm opacity-70">Let's set up the basics before you start managing students and fees.</p>
        </div>
        
        <form onSubmit={onSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Row 1: School name | School type */}
          <div>
            <label className="text-sm font-medium">School name *</label>
            <input
              className="input mt-1"
              value={form.name}
              onChange={(e) => {
                const newName = e.target.value;
                setForm({ 
                  ...form, 
                  name: newName,
                  short_code: shortCodeManuallyEdited ? form.short_code : generateShortCode(newName)
                });
              }}
              placeholder="e.g., Imara Primary School"
              required
            />
          </div>

          <div>
            <label className="text-sm font-medium">School type *</label>
            <select 
              className="input mt-1" 
              value={form.boarding_type}
              onChange={(e) => setForm({ ...form, boarding_type: e.target.value as any })}
              required
            >
              <option value="" disabled>Select school type</option>
              <option value="DAY">Day school</option>
              <option value="BOARDING">Boarding school</option>
              <option value="BOTH">Day & Boarding</option>
            </select>
          </div>

          {/* Row 2: Short code | Gender */}
          <div>
            <label className="text-sm font-medium">Short code</label>
            <input 
              className="input mt-1" 
              value={form.short_code}
              onChange={(e) => {
                setShortCodeManuallyEdited(true);
                setForm({ ...form, short_code: e.target.value.toUpperCase() });
              }}
              placeholder="IMARA"
              maxLength={10}
            />
            <p className="text-xs opacity-60 mt-1">Used for reports and student IDs</p>
          </div>

          <div>
            <label className="text-sm font-medium">Gender *</label>
            <select 
              className="input mt-1" 
              value={form.gender_type}
              onChange={(e) => setForm({ ...form, gender_type: e.target.value as any })}
              required
            >
              <option value="" disabled>Select gender type</option>
              <option value="MIXED">Mixed (Boys & Girls)</option>
              <option value="BOYS">Boys only</option>
              <option value="GIRLS">Girls only</option>
            </select>
          </div>

          {/* Row 3: Official email | Phone */}
          <div>
            <label className="text-sm font-medium">Official email</label>
            <input 
              type="email"
              className="input mt-1" 
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="admin@school.ke" 
            />
          </div>

          <div>
            <label className="text-sm font-medium">Phone</label>
            <input 
              type="tel"
              className="input mt-1" 
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              placeholder="+254..." 
            />
          </div>

          {/* Row 4: Address (full width) */}
          <div className="md:col-span-2">
            <label className="text-sm font-medium">Address</label>
            <input 
              className="input mt-1" 
              value={form.address}
              onChange={(e) => setForm({ ...form, address: e.target.value })}
              placeholder="School address / Location" 
            />
          </div>

          {/* Row 5: Currency | Academic start date */}
          <div>
            <label className="text-sm font-medium">Currency</label>
            <select 
              className="input mt-1" 
              value={form.currency}
              onChange={(e) => setForm({ ...form, currency: e.target.value })}
            >
              <option value="KES">KES - Kenyan Shilling</option>
              <option value="USD">USD - US Dollar</option>
              <option value="UGX">UGX - Ugandan Shilling</option>
              <option value="TZS">TZS - Tanzanian Shilling</option>
            </select>
          </div>

          <div>
            <label className="text-sm font-medium">Academic year start date *</label>
            <input 
              type="date" 
              className="input mt-1" 
              value={form.academic_year_start}
              onChange={(e) => setForm({ ...form, academic_year_start: e.target.value })}
              required
            />
            <p className="text-xs opacity-60 mt-1">
              Most Kenyan schools start in January
            </p>
          </div>

          {/* Submit button (full width) */}
          <div className="md:col-span-2">
            <button 
              type="submit"
              className="btn-primary w-full" 
              disabled={loading || !form.name.trim() || !form.academic_year_start || !form.boarding_type || !form.gender_type}
            >
              {loading ? "Creating school & setting up academic calendar…" : "Create school"}
            </button>
          </div>
          
          {/* Error message (full width) */}
          {err && (
            <div className="md:col-span-2 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 p-3 rounded">
              {err}
            </div>
          )}
        </form>
      </div>
    </div>
  );
}

export default function OnboardingSchoolPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <OnboardingSchoolForm />
    </Suspense>
  );
}