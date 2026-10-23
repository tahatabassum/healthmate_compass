import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
import api from '../lib/api';
import { ReportCard } from '../components/reports/ReportCard';
import type { ReportItem } from '../components/reports/ReportCard';
import { ViewAllReportsModal } from '../components/reports/ViewAllReportsModal';

export const HomeDashboardPage: React.FC = () => {
  const { i18n } = useTranslation();
  const { user, profile } = useAuth();
  const isUrdu = i18n.language.startsWith('ur');

  const displayName = profile?.full_name || user?.user_metadata?.full_name || user?.email?.split('@')[0] || 'Patient';

  const actionCards = [
    {
      to: '/translate',
      title: 'Analyze Document',
      subtitle: 'Upload diagnostic lab tests or doctor prescriptions for clear translation and physiological safety verification.',
      icon: 'description',
      badge: 'Multimodal',
      color: 'bg-primary-container text-on-primary-container',
    },
    {
      to: '/consult',
      title: 'AI Doctor Chat',
      subtitle: 'Gemma 4 clinical assistant with emergency triage guardrails and dynamic memory.',
      icon: 'smart_toy',
      badge: 'Gemma 4',
      color: 'bg-secondary-container text-on-secondary-container',
    },
    {
      to: '/doctors',
      title: 'Find Doctors',
      subtitle: 'Locate top-rated clinics, hospitals, and specialists across Pakistan with verified contact details.',
      icon: 'location_on',
      badge: 'Pakistan',
      color: 'bg-tertiary-container text-on-tertiary-container',
    },
    {
      to: '/memory',
      title: 'Health Memory',
      subtitle: 'Review confirmed clinical facts, active medications, and diagnostic timelines stored in your record.',
      icon: 'history_edu',
      badge: 'Timeline',
      color: 'bg-surface-container-high text-primary',
    },
  ];

  const [reports, setReports] = useState<ReportItem[]>([]);
  const [loadingReports, setLoadingReports] = useState(true);
  const [reportsError, setReportsError] = useState<string | null>(null);
  const [showViewAllModal, setShowViewAllModal] = useState(false);

  const fetchReports = async () => {
    setLoadingReports(true);
    setReportsError(null);
    try {
      const res = await api.get('/api/reports');
      setReports(res.data || []);
    } catch (err) {
      console.error('Failed to load reports:', err);
      setReportsError('Failed to load reports');
    } finally {
      setLoadingReports(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, [user?.id]);

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 md:py-8 space-y-8">
      {/* ── HERO BANNER (Stitch Guardian Greeting) ─────────────────────────── */}
      <div className="bg-surface-container-lowest border border-outline-variant/60 rounded-3xl p-6 md:p-8 shadow-xs relative overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10">
          <div>
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-container text-primary text-xs font-bold mb-3 border border-outline-variant/40">
              <span
                className="material-symbols-outlined text-sm text-primary"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                verified_user
              </span>
              <span>Gemma 4 Clinical Assistant Active</span>
            </div>

            <h1 className="text-2xl md:text-3xl font-bold text-on-surface tracking-tight">
              {isUrdu ? (
                <>خوش آمدید، {displayName}</>
              ) : (
                <>Welcome back, {displayName}</>
              )}
            </h1>
            <p className="text-xs md:text-sm text-secondary mt-1.5 max-w-xl leading-relaxed">
              {isUrdu
                ? 'اپنی صحت کا باآسانی خیال رکھیں۔ ہیلتھ میٹ کمپاس آپ کی رپورٹس کا درست تجزیہ کرتا ہے اور صحیح ڈاکٹر تک رہنمائی کرتا ہے۔'
                : 'Understand clinical reports with code-verified reference ranges, consult AI doctor with emergency safeguards, and find nearby specialists on Google Maps.'}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link
              to="/translate"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-primary-container text-on-primary-container font-bold text-xs md:text-sm shadow-xs hover:opacity-95 active:scale-95 transition-all"
            >
              <span
                className="material-symbols-outlined text-lg"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                upload_file
              </span>
              <span>Upload New Report</span>
            </Link>

            <Link
              to="/consult"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-surface-container hover:bg-surface-container-high text-on-surface font-bold text-xs md:text-sm border border-outline-variant/60 shadow-xs transition-all"
            >
              <span className="material-symbols-outlined text-lg text-primary">chat</span>
              <span>Start Consult</span>
            </Link>
          </div>
        </div>
      </div>

      {/* ── 4 PRIMARY ACTION CARDS (Stitch 2x2 Grid) ───────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base md:text-lg font-bold text-on-surface flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-xl">grid_view</span>
            <span>Clinical Care Features</span>
          </h2>
          <span className="text-xs text-secondary font-medium">
            AI + Code Rule Grounding
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {actionCards.map((card, idx) => (
            <Link
              key={idx}
              to={card.to}
              className="bg-surface-container-lowest border border-outline-variant/60 hover:border-primary/50 hover:shadow-md rounded-3xl p-5 flex flex-col justify-between transition-all duration-200 group active:scale-98"
            >
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div
                    className={`w-12 h-12 rounded-2xl flex items-center justify-center shadow-xs group-hover:scale-105 transition-transform ${card.color}`}
                  >
                    <span
                      className="material-symbols-outlined text-2xl"
                      style={{ fontVariationSettings: "'FILL' 1" }}
                    >
                      {card.icon}
                    </span>
                  </div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-secondary bg-surface-container px-2 py-0.5 rounded-full border border-outline-variant/40">
                    {card.badge}
                  </span>
                </div>

                <h3 className="font-bold text-on-surface text-base group-hover:text-primary transition-colors">
                  {card.title}
                </h3>
                <p className="text-xs text-secondary mt-1.5 leading-relaxed line-clamp-3">
                  {card.subtitle}
                </p>
              </div>

              <div className="mt-5 pt-3 border-t border-outline-variant/40 flex items-center justify-between text-xs font-bold text-primary">
                <span>Open Tool</span>
                <span className="material-symbols-outlined text-base group-hover:translate-x-1 transition-transform">
                  arrow_forward
                </span>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* ── RECENT REPORTS SECTION (Stitch List View) ───────────────────────── */}
      <div className="bg-surface-container-lowest border border-outline-variant/60 rounded-3xl p-6 shadow-xs">
        <div className="flex items-center justify-between pb-4 border-b border-outline-variant/40">
          <div>
            <h2 className="text-base md:text-lg font-bold text-on-surface flex items-center gap-2">
              <span className="material-symbols-outlined text-primary text-xl">description</span>
              <span>Recent Reports</span>
            </h2>
            <p className="text-xs text-secondary mt-0.5">
              Verified clinical records for {displayName}
            </p>
          </div>

          <div className="flex items-center gap-3">
            {reports.length > 0 && (
              <button
                type="button"
                onClick={() => setShowViewAllModal(true)}
                className="text-xs font-bold text-secondary hover:text-primary transition-colors cursor-pointer"
              >
                View all ({reports.length})
              </button>
            )}
            <Link
              to="/translate"
              className="text-xs font-bold text-primary hover:underline flex items-center gap-1"
            >
              <span>Upload New</span>
              <span className="material-symbols-outlined text-sm">add</span>
            </Link>
          </div>
        </div>

        {/* Loading skeleton */}
        {loadingReports && (
          <div className="space-y-3 mt-4">
            {[1, 2].map((i) => (
              <div
                key={i}
                className="animate-pulse flex items-center justify-between p-4 rounded-2xl bg-surface-container-low/40"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-2xl bg-surface-container shrink-0" />
                  <div className="space-y-2">
                    <div className="h-4 w-48 bg-surface-container rounded" />
                    <div className="h-3 w-32 bg-surface-container rounded" />
                  </div>
                </div>
                <div className="h-6 w-20 bg-surface-container rounded-full" />
              </div>
            ))}
          </div>
        )}

        {/* Error state */}
        {!loadingReports && reportsError && (
          <div className="py-8 text-center">
            <p className="text-xs text-error font-medium">{reportsError}</p>
            <button
              type="button"
              onClick={fetchReports}
              className="mt-2 text-xs font-bold text-primary hover:underline cursor-pointer"
            >
              Retry
            </button>
          </div>
        )}

        {/* Empty state */}
        {!loadingReports && !reportsError && reports.length === 0 && (
          <div className="py-10 px-4 text-center flex flex-col items-center">
            <div className="w-12 h-12 rounded-2xl bg-surface-container flex items-center justify-center text-secondary mb-3">
              <span className="material-symbols-outlined text-2xl">post_add</span>
            </div>
            <h3 className="text-sm font-bold text-on-surface">No reports or prescriptions yet</h3>
            <p className="text-xs text-secondary mt-1 max-w-sm">
              Upload your lab test or prescription to get clear explanations and safety checks.
            </p>
            <Link
              to="/translate"
              className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-primary text-on-primary text-xs font-bold shadow-xs hover:bg-primary/90 transition-colors"
            >
              <span className="material-symbols-outlined text-sm">upload_file</span>
              <span>Upload your first report</span>
            </Link>
          </div>
        )}

        {/* Report List (Top 2 items) */}
        {!loadingReports && !reportsError && reports.length > 0 && (
          <div className="divide-y divide-outline-variant/40 mt-2">
            {reports.slice(0, 2).map((rep) => (
              <ReportCard key={rep.id} report={rep} />
            ))}
          </div>
        )}
      </div>

      {/* View All Modal */}
      <ViewAllReportsModal
        isOpen={showViewAllModal}
        onClose={() => setShowViewAllModal(false)}
        reports={reports}
      />

      {/* ── PERSONAL HEALTH PROFILE SUMMARY ─────────────────────────────────── */}
      <div className="bg-surface-container-lowest border border-outline-variant/60 rounded-3xl p-6 shadow-xs">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base md:text-lg font-bold text-on-surface flex items-center gap-2">
              <span className="material-symbols-outlined text-primary text-xl">account_circle</span>
              <span>Personal Health Profile Summary</span>
            </h2>
            <p className="text-xs text-secondary mt-0.5">
              1-User health record linked to your account ({user?.email})
            </p>
          </div>

          <Link
            to="/memory"
            className="text-xs font-bold text-primary hover:underline flex items-center gap-1"
          >
            <span>Update Profile</span>
            <span className="material-symbols-outlined text-sm">edit</span>
          </Link>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-2xl bg-surface-container-low border border-outline-variant/50">
            <span className="text-[10px] font-bold uppercase tracking-wider text-secondary">Full Name</span>
            <p className="text-sm font-bold text-on-surface mt-1 truncate">{displayName}</p>
          </div>

          <div className="p-4 rounded-2xl bg-surface-container-low border border-outline-variant/50">
            <span className="text-[10px] font-bold uppercase tracking-wider text-secondary">Blood Group</span>
            <p className="text-sm font-bold text-on-surface mt-1">{profile?.blood_group || 'Not specified'}</p>
          </div>

          <div className="p-4 rounded-2xl bg-surface-container-low border border-outline-variant/50">
            <span className="text-[10px] font-bold uppercase tracking-wider text-secondary">Gender</span>
            <p className="text-sm font-bold text-on-surface mt-1 capitalize">{profile?.gender || 'Not specified'}</p>
          </div>

          <div className="p-4 rounded-2xl bg-surface-container-low border border-outline-variant/50">
            <span className="text-[10px] font-bold uppercase tracking-wider text-secondary">Allergies / Conditions</span>
            <p className="text-sm font-bold text-on-surface mt-1">
              {(profile?.allergies?.length || 0) + (profile?.chronic_conditions?.length || 0)} recorded
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
