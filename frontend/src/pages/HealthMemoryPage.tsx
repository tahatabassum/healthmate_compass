import React, { useState, useEffect } from 'react';
import api from '../lib/api';
import { useAuth } from '../context/AuthContext';

interface MemoryFact {
  id: string;
  patient_id?: string;
  fact_type: string;
  key: string;
  value: string;
  status?: string;
  created_at?: string;
}

export const HealthMemoryPage: React.FC = () => {
  const { user, profile, updateProfile, refreshProfile } = useAuth();
  const [facts, setFacts] = useState<MemoryFact[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAddFact, setShowAddFact] = useState(false);
  const [editingProfile, setEditingProfile] = useState(false);

  // Profile edit fields
  const [editName, setEditName] = useState(profile?.full_name || '');
  const [editGender, setEditGender] = useState(profile?.gender || 'male');
  const [editBloodGroup, setEditBloodGroup] = useState(profile?.blood_group || 'B+');
  const [savingProfile, setSavingProfile] = useState(false);

  // New fact form
  const [newFactType, setNewFactType] = useState('condition');
  const [newFactKey, setNewFactKey] = useState('');
  const [newFactValue, setNewFactValue] = useState('');

  useEffect(() => {
    if (profile) {
      setEditName(profile.full_name || '');
      setEditGender(profile.gender || 'male');
      setEditBloodGroup(profile.blood_group || 'B+');
    }
  }, [profile]);

  const fetchFacts = async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/memory');
      setFacts(res.data || []);
    } catch (err) {
      console.error('Error fetching memory facts:', err);
      setFacts([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFacts();
  }, [profile?.id]);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingProfile(true);
    await updateProfile({
      full_name: editName.trim(),
      gender: editGender,
      blood_group: editBloodGroup,
    });
    setSavingProfile(false);
    setEditingProfile(false);
    await refreshProfile();
  };

  const handleDeleteFact = async (factId: string) => {
    try {
      await api.delete(`/api/memory/${factId}`);
      setFacts((prev) => prev.filter((f) => f.id !== factId));
    } catch (err) {
      console.error('Error deleting fact:', err);
      setFacts((prev) => prev.filter((f) => f.id !== factId));
    }
  };

  const handleAddFact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFactKey.trim() || !newFactValue.trim()) return;

    try {
      const res = await api.post('/api/memory', {
        fact_type: newFactType,
        key: newFactKey.trim(),
        value: newFactValue.trim(),
      });
      if (res.data) {
        setFacts((prev) => [res.data, ...prev.filter((f) => f.key.toLowerCase() !== newFactKey.trim().toLowerCase())]);
      }
      setNewFactKey('');
      setNewFactValue('');
      setShowAddFact(false);
    } catch (err) {
      console.error('Failed to save memory fact:', err);
    }
  };

  const [filterCategory, setFilterCategory] = useState<'all' | 'conditions' | 'summaries' | 'medications'>('all');

  const parseFactToDisplay = (fact: MemoryFact) => {
    const fType = (fact.fact_type || '').toLowerCase();
    const rawVal = (fact.value || '').trim();

    // 1. Change Log (raw JSON from profile changes)
    if (fType === 'change_log' || (rawVal.startsWith('{') && rawVal.includes('target_name'))) {
      try {
        const data = JSON.parse(rawVal);
        const target = data.target_name || fact.key;
        const isResolved = data.operation === 'resolve';
        const points: string[] = [];

        if (isResolved) {
          points.push('Status: Resolved in medical profile');
        } else if (data.operation === 'add') {
          points.push('Status: Active medical condition recorded');
        } else if (data.operation) {
          points.push(`Status: ${data.operation}`);
        }

        if (data.evidence_quote) {
          points.push(`Patient noted: "${data.evidence_quote}"`);
        }
        if (data.new_value?.resolved_at) {
          points.push(`Resolved on: ${data.new_value.resolved_at}`);
        } else if (data.new_value?.started_at) {
          points.push(`Recorded on: ${data.new_value.started_at}`);
        }

        return {
          id: fact.id,
          category: 'conditions',
          categoryLabel: isResolved ? 'Resolved Condition' : 'Profile Update',
          badgeClass: isResolved ? 'bg-[#DCFCE7] text-[#16A34A]' : 'bg-primary-container text-on-primary-container',
          icon: isResolved ? 'check_circle' : 'update',
          title: target.replace(/[_-]+/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()),
          keyPoints: points.length > 0 ? points : ['Profile update logged'],
        };
      } catch {
        // Fall through if not valid JSON
      }
    }

    // 2. Chat Summary (consultation summary)
    if (fType === 'chat_summary') {
      let title = 'Consultation Takeaway';
      const lowerVal = rawVal.toLowerCase();
      if (lowerVal.includes('arm') && lowerVal.includes('fracture')) {
        title = lowerVal.includes('recovering') ? 'Arm Fracture Recovery' : 'Arm Fracture Assessment';
      } else if (lowerVal.includes('hand') && lowerVal.includes('fracture')) {
        title = 'Hand Fracture & Care';
      } else if (lowerVal.includes('headache')) {
        title = 'Headache Consultation';
      } else if (lowerVal.includes('blood pressure') || lowerVal.includes('hypertension')) {
        title = 'Blood Pressure Review';
      } else if (lowerVal.includes('diabetes') || lowerVal.includes('glucose') || lowerVal.includes('sugar')) {
        title = 'Blood Glucose Consultation';
      } else if (lowerVal.includes('fever')) {
        title = 'Fever Assessment';
      }

      // Split into clean, concise clinical key points
      const sentences = rawVal
        .split(/(?<=[.?!])\s+/)
        .map((s) => s.trim())
        .filter((s) => s.length > 5);

      const keyPoints = sentences.map((s) => {
        const cleaned = s
          .replace(/^The patient reported /i, '')
          .replace(/^The user reported /i, '')
          .replace(/^The discussion noted /i, '')
          .replace(/^The assistant advised /i, 'Advice: ')
          .replace(/^The consultation concluded with advice to /i, 'Advice: ')
          .replace(/^The patient was advised to /i, 'Advice: ')
          .replace(/^The patient was also advised to /i, 'Advice: ')
          .replace(/^The patient inquired about /i, 'Discussed: ')
          .replace(/\.$/, '')
          .trim();
        return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
      });

      return {
        id: fact.id,
        category: 'summaries',
        categoryLabel: 'Past Consultation',
        badgeClass: 'bg-primary-container text-on-primary-container',
        icon: 'history_edu',
        title,
        keyPoints: keyPoints.length > 0 ? keyPoints : [rawVal],
      };
    }

    // 3. Condition
    if (fType === 'condition') {
      const cleanKey = fact.key.replace(/[_-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
      const cleanVal = fact.value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
      return {
        id: fact.id,
        category: 'conditions',
        categoryLabel: 'Medical Condition',
        badgeClass: 'bg-[#FEF3C7] text-[#D97706]',
        icon: 'favorite',
        title: cleanKey,
        keyPoints: [cleanVal.includes('Active') || cleanVal.includes('Diagnosed') ? cleanVal : `Status: ${cleanVal}`],
      };
    }

    // 4. Allergy
    if (fType === 'allergy') {
      const cleanKey = fact.key.replace(/[_-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
      const cleanVal = fact.value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
      return {
        id: fact.id,
        category: 'medications',
        categoryLabel: 'Allergy Warning',
        badgeClass: 'bg-error-container text-on-error-container',
        icon: 'shield',
        title: cleanKey,
        keyPoints: [`Reaction / Severity: ${cleanVal}`],
      };
    }

    // 5. Medication
    if (fType === 'medication') {
      const cleanKey = fact.key.replace(/[_-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
      return {
        id: fact.id,
        category: 'medications',
        categoryLabel: 'Active Medication',
        badgeClass: 'bg-[#DCFCE7] text-[#16A34A]',
        icon: 'medication',
        title: cleanKey,
        keyPoints: [fact.value],
      };
    }

    // 6. Generic / Event
    const cleanKey = fact.key.replace(/[_-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
    const cleanVal = fact.value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
    return {
      id: fact.id,
      category: 'conditions',
      categoryLabel: fact.fact_type ? fact.fact_type.replace(/[_-]+/g, ' ').toUpperCase() : 'HEALTH FACT',
      badgeClass: 'bg-surface-container text-on-surface-variant',
      icon: 'verified',
      title: cleanKey,
      keyPoints: [cleanVal],
    };
  };

  const displayName = profile?.full_name || user?.user_metadata?.full_name || user?.email?.split('@')[0] || 'Patient';

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 md:py-8 space-y-8">
      {/* ── HEADER ────────────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-container text-primary text-xs font-bold mb-2 border border-outline-variant/50">
            <span
              className="material-symbols-outlined text-sm text-primary"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              history_edu
            </span>
            <span>Permanent Cross-Session Clinical Memory</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold text-on-surface tracking-tight">
            Personal Health Profile & Memory
          </h1>
          <p className="text-xs md:text-sm text-secondary mt-1 max-w-2xl">
            HealthMate maintains a verified 1-user medical record. Every condition, allergy, and test result is permanently remembered so every AI consultation is grounded in your medical history.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setShowAddFact(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-2xl bg-primary-container text-on-primary-container hover:opacity-95 font-bold text-xs shadow-xs transition-all shrink-0 active:scale-98"
          >
            <span className="material-symbols-outlined text-base">add</span>
            <span>Add Health Fact</span>
          </button>
        </div>
      </div>

      {/* ── PROFILE CARD & EDITOR ─────────────────────────────────────────── */}
      <div className="bg-surface-container-lowest rounded-3xl border border-outline-variant/60 shadow-xs p-6 md:p-8">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 border-b border-outline-variant/40">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-primary">
              Your Health Profile (1-User Isolated)
            </span>
            <h2 className="text-xl md:text-2xl font-bold text-on-surface mt-0.5">
              {displayName}
            </h2>
            <p className="text-xs text-secondary mt-1">
              Account: {user?.email} • Gender: <span className="capitalize">{profile?.gender || 'Not specified'}</span> • Blood: {profile?.blood_group || 'Not specified'}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setEditingProfile(!editingProfile)}
              className="px-3.5 py-2 rounded-xl border border-outline-variant/60 hover:border-primary text-xs font-bold text-primary flex items-center gap-1.5 transition-colors"
            >
              <span className="material-symbols-outlined text-sm">
                {editingProfile ? 'close' : 'edit'}
              </span>
              <span>{editingProfile ? 'Cancel' : 'Edit Profile'}</span>
            </button>
          </div>
        </div>

        {/* Profile Edit Inline Form */}
        {editingProfile && (
          <form onSubmit={handleSaveProfile} className="mt-6 p-4 rounded-2xl bg-surface-container-low border border-primary/30 grid grid-cols-1 sm:grid-cols-4 gap-3.5 animate-in fade-in">
            <div>
              <label className="block text-[11px] font-bold text-secondary uppercase tracking-wider mb-1">
                Full Name
              </label>
              <input
                type="text"
                required
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="w-full bg-surface-container-lowest border border-outline-variant/60 rounded-xl px-3 py-2 text-xs text-on-surface focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-[11px] font-bold text-secondary uppercase tracking-wider mb-1">
                Gender
              </label>
              <select
                value={editGender}
                onChange={(e) => setEditGender(e.target.value)}
                className="w-full bg-surface-container-lowest border border-outline-variant/60 rounded-xl px-3 py-2 text-xs font-semibold text-on-surface focus:outline-none"
              >
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-bold text-secondary uppercase tracking-wider mb-1">
                Blood Group
              </label>
              <select
                value={editBloodGroup}
                onChange={(e) => setEditBloodGroup(e.target.value)}
                className="w-full bg-surface-container-lowest border border-outline-variant/60 rounded-xl px-3 py-2 text-xs font-semibold text-on-surface focus:outline-none"
              >
                <option value="A+">A+</option>
                <option value="A-">A-</option>
                <option value="B+">B+</option>
                <option value="B-">B-</option>
                <option value="O+">O+</option>
                <option value="O-">O-</option>
                <option value="AB+">AB+</option>
                <option value="AB-">AB-</option>
              </select>
            </div>

            <div className="flex items-end">
              <button
                type="submit"
                disabled={savingProfile}
                className="w-full py-2 px-4 rounded-xl bg-primary text-on-primary font-bold text-xs shadow-xs hover:opacity-95 disabled:opacity-50"
              >
                {savingProfile ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </form>
        )}

        {/* Add Health Fact Form Modal */}
        {showAddFact && (
          <div className="mt-6 p-6 bg-surface-container-low rounded-3xl border border-primary/40 shadow-sm animate-in fade-in">
            <h3 className="font-bold text-on-surface text-base mb-4 flex items-center gap-2">
              <span className="material-symbols-outlined text-primary text-xl">psychology</span>
              <span>Remember New Health Fact</span>
            </h3>
            <form onSubmit={handleAddFact} className="grid grid-cols-1 sm:grid-cols-4 gap-3.5">
              <div>
                <label className="block text-[11px] font-bold text-secondary uppercase tracking-wider mb-1">
                  Fact Type
                </label>
                <select
                  value={newFactType}
                  onChange={(e) => setNewFactType(e.target.value)}
                  className="w-full bg-surface-container-lowest border border-outline-variant/60 rounded-2xl px-3.5 py-2.5 text-xs font-semibold text-on-surface focus:outline-none"
                >
                  <option value="condition">Condition</option>
                  <option value="allergy">Allergy</option>
                  <option value="medication">Medication</option>
                  <option value="lifestyle">Lifestyle</option>
                  <option value="preference">Preference</option>
                  <option value="general">General Note</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-secondary uppercase tracking-wider mb-1">
                  Key / Subject
                </label>
                <input
                  type="text"
                  required
                  value={newFactKey}
                  onChange={(e) => setNewFactKey(e.target.value)}
                  placeholder="e.g. Asthma, Penicillin"
                  className="w-full bg-surface-container-lowest border border-outline-variant/60 rounded-2xl px-3.5 py-2.5 text-xs text-on-surface focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-secondary uppercase tracking-wider mb-1">
                  Details / Notes
                </label>
                <input
                  type="text"
                  required
                  value={newFactValue}
                  onChange={(e) => setNewFactValue(e.target.value)}
                  placeholder="e.g. Inhaler as needed"
                  className="w-full bg-surface-container-lowest border border-outline-variant/60 rounded-2xl px-3.5 py-2.5 text-xs text-on-surface focus:outline-none"
                />
              </div>

              <div className="flex items-end gap-2">
                <button
                  type="submit"
                  className="flex-1 py-2.5 px-4 rounded-2xl bg-primary-container text-on-primary-container font-bold text-xs shadow-xs"
                >
                  Save Fact
                </button>
                <button
                  type="button"
                  onClick={() => setShowAddFact(false)}
                  className="py-2.5 px-3 rounded-2xl border border-outline-variant/60 text-xs font-semibold text-secondary hover:bg-surface-container"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Facts List */}
        <div className="mt-8">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
            <div>
              <h3 className="font-bold text-on-surface text-base sm:text-lg">
                Active Medical Facts & Previous Memory
              </h3>
              <p className="text-xs text-secondary mt-0.5">
                Key medical takeaways permanently remembered for your AI consultations
              </p>
            </div>

            {loading && (
              <span className="text-xs text-secondary flex items-center gap-1">
                <span className="material-symbols-outlined text-sm animate-spin">refresh</span>
                <span>Loading memory facts…</span>
              </span>
            )}
          </div>

          {/* Filter Pills */}
          <div className="flex flex-wrap items-center gap-2 mb-5">
            {[
              { id: 'all', label: 'All Memory Points', icon: 'auto_awesome' },
              { id: 'conditions', label: 'Conditions & Updates', icon: 'favorite' },
              { id: 'summaries', label: 'Consultation Takeaways', icon: 'history_edu' },
              { id: 'medications', label: 'Medications & Allergies', icon: 'medication' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setFilterCategory(tab.id as any)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                  filterCategory === tab.id
                    ? 'bg-primary text-on-primary shadow-xs'
                    : 'bg-surface-container-low text-secondary hover:text-on-surface hover:bg-surface-container border border-outline-variant/50'
                }`}
              >
                <span className="material-symbols-outlined text-sm">{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </div>

          {/* Cards Grid */}
          {facts.length === 0 ? (
            <div className="text-center py-12 bg-surface-container-low rounded-2xl border border-outline-variant/40">
              <span className="material-symbols-outlined text-3xl text-secondary mb-2">folder_off</span>
              <p className="text-xs text-secondary">No memory facts recorded yet.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {facts
                .map((f) => parseFactToDisplay(f))
                .filter((item) => filterCategory === 'all' || item.category === filterCategory)
                .map((item) => (
                  <div
                    key={item.id}
                    className="p-5 rounded-2xl bg-surface-container-low border border-outline-variant/60 hover:border-primary/40 transition-all flex flex-col justify-between gap-3 shadow-2xs hover:shadow-xs"
                  >
                    <div>
                      {/* Card Top: Icon + Badge + Delete Button */}
                      <div className="flex items-center justify-between gap-2 mb-2.5">
                        <div className="flex items-center gap-2">
                          <div className="w-7 h-7 rounded-lg bg-surface-container-lowest border border-outline-variant/60 flex items-center justify-center shrink-0">
                            <span
                              className="material-symbols-outlined text-primary text-base"
                              style={{ fontVariationSettings: "'FILL' 1" }}
                            >
                              {item.icon}
                            </span>
                          </div>
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${item.badgeClass}`}>
                            {item.categoryLabel}
                          </span>
                        </div>

                        <button
                          onClick={() => handleDeleteFact(item.id)}
                          className="text-secondary hover:text-error p-1 rounded-lg transition-colors"
                          title="Remove memory fact"
                        >
                          <span className="material-symbols-outlined text-base">delete</span>
                        </button>
                      </div>

                      {/* Clean Human Title */}
                      <h4 className="font-bold text-on-surface text-sm sm:text-base mb-2">
                        {item.title}
                      </h4>

                      {/* Concise Bulleted Key Points */}
                      <ul className="space-y-1.5 text-xs text-on-surface-variant leading-relaxed">
                        {item.keyPoints.map((point, i) => (
                          <li key={i} className="flex items-start gap-1.5">
                            <span className="text-primary font-bold text-sm leading-tight shrink-0">•</span>
                            <span>{point}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
