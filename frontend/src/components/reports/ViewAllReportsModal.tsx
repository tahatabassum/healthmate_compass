import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { ReportCard } from './ReportCard';
import type { ReportItem } from './ReportCard';

interface ViewAllReportsModalProps {
  isOpen: boolean;
  onClose: () => void;
  reports: ReportItem[];
  onDeleteReport?: (id: string) => void;
}

export const ViewAllReportsModal: React.FC<ViewAllReportsModalProps> = ({
  isOpen,
  onClose,
  reports,
  onDeleteReport,
}) => {
  const { i18n } = useTranslation();
  const isUrdu = i18n.language.startsWith('ur');

  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<'all' | 'lab' | 'prescription'>('all');
  const [sortOrder, setSortOrder] = useState<'newest' | 'oldest'>('newest');

  const modalRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Lock body scroll when modal is open and handle Esc key
  useEffect(() => {
    if (!isOpen) return;

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    // Focus input on open
    setTimeout(() => {
      searchInputRef.current?.focus();
    }, 50);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  // Filter & Search Logic
  const filtered = reports.filter((rep) => {
    const isPrescription =
      rep.document_type === 'prescription' ||
      (rep.medicines && rep.medicines.length > 0 && (!rep.values || rep.values.length === 0));

    if (filterType === 'lab' && isPrescription) return false;
    if (filterType === 'prescription' && !isPrescription) return false;

    if (!searchQuery.trim()) return true;

    const q = searchQuery.toLowerCase().trim();
    const labName = (rep.lab_name || '').toLowerCase();
    const docName = (rep.doctor_name || '').toLowerCase();
    const testNames = (rep.values || []).map((v) => v.test_name.toLowerCase()).join(' ');
    const medNames = (rep.medicines || []).map((m) => m.name.toLowerCase()).join(' ');

    return (
      labName.includes(q) ||
      docName.includes(q) ||
      testNames.includes(q) ||
      medNames.includes(q) ||
      (rep.report_date && rep.report_date.includes(q))
    );
  });

  // Sort Logic
  const sorted = [...filtered].sort((a, b) => {
    const dateA = a.report_date || a.created_at || '';
    const dateB = b.report_date || b.created_at || '';
    if (sortOrder === 'newest') {
      return dateB.localeCompare(dateA);
    }
    return dateA.localeCompare(dateB);
  });

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-all-reports-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-0 md:p-4 bg-black/50 backdrop-blur-xs transition-opacity"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/* Modal Canvas: Desktop centered (max-w ~720px, max-h 80vh), Mobile full screen (100dvh) */}
      <div
        ref={modalRef}
        className="w-full md:max-w-[720px] h-[100dvh] md:h-auto md:max-h-[85vh] bg-surface-container-lowest md:rounded-3xl border border-outline-variant/60 shadow-2xl flex flex-col overflow-hidden animate-in zoom-in-95 duration-200"
      >
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-outline-variant/60 flex items-center justify-between gap-3 shrink-0 bg-surface-container-low/40">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-primary-container text-on-primary-container flex items-center justify-center shadow-xs">
              <span className="material-symbols-outlined text-xl" style={{ fontVariationSettings: "'FILL' 1" }}>
                folder_open
              </span>
            </div>
            <div>
              <h2 id="modal-all-reports-title" className="text-base sm:text-lg font-bold text-on-surface">
                {isUrdu ? 'تمام محفوظ شدہ رپورٹس اور نسخے' : 'All Saved Reports & Prescriptions'}
              </h2>
              <p className="text-xs text-secondary">
                {isUrdu
                  ? `${reports.length} طبی دستاویزات محفوظ ہیں`
                  : `${reports.length} total medical records in database`}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-2xl text-secondary hover:text-on-surface hover:bg-surface-container transition-colors"
            aria-label={isUrdu ? 'بند کریں' : 'Close Modal'}
          >
            <span className="material-symbols-outlined text-xl">close</span>
          </button>
        </div>

        {/* Controls: Search Bar + Filter Tabs + Sort Toggle */}
        <div className="p-4 sm:p-5 border-b border-outline-variant/40 space-y-3 shrink-0 bg-surface-container-lowest">
          {/* Search Bar */}
          <div className="relative">
            <span className="material-symbols-outlined absolute start-3.5 top-1/2 -translate-y-1/2 text-secondary text-lg">
              search
            </span>
            <input
              ref={searchInputRef}
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={
                isUrdu
                  ? 'رپورٹ کا نام، لیب، ڈاکٹر یا ٹیسٹ تلاش کریں...'
                  : 'Search by report, lab, doctor, or test name...'
              }
              className="w-full bg-surface-container-low border border-outline-variant/60 rounded-2xl ps-10 pe-9 py-2.5 text-xs sm:text-sm text-on-surface placeholder:text-secondary focus:outline-none focus:ring-2 focus:ring-primary/40"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute end-3 top-1/2 -translate-y-1/2 text-secondary hover:text-on-surface p-1"
                title="Clear"
              >
                <span className="material-symbols-outlined text-base">cancel</span>
              </button>
            )}
          </div>

          {/* Filter Tabs & Sort Toggle */}
          <div className="flex flex-wrap items-center justify-between gap-2.5">
            <div className="flex items-center gap-1.5 p-1 rounded-xl bg-surface-container-low border border-outline-variant/60">
              {[
                { id: 'all', label: isUrdu ? 'تمام' : 'All' },
                { id: 'lab', label: isUrdu ? 'لیب رپورٹس' : 'Lab Reports' },
                { id: 'prescription', label: isUrdu ? 'نسخے' : 'Prescriptions' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setFilterType(tab.id as any)}
                  className={`min-h-[36px] px-3 py-1 rounded-lg text-xs font-bold transition-all ${
                    filterType === tab.id
                      ? 'bg-primary-container text-on-primary-container shadow-xs'
                      : 'text-secondary hover:text-on-surface'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <button
              onClick={() => setSortOrder(sortOrder === 'newest' ? 'oldest' : 'newest')}
              className="min-h-[36px] inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-outline-variant/60 text-xs font-semibold text-secondary hover:text-on-surface hover:bg-surface-container-low transition-colors"
            >
              <span className="material-symbols-outlined text-sm">swap_vert</span>
              <span>{sortOrder === 'newest' ? (isUrdu ? 'تازہ ترین' : 'Newest first') : (isUrdu ? 'پرانی ترین' : 'Oldest first')}</span>
            </button>
          </div>
        </div>

        {/* Scrollable Report Rows */}
        <div className="flex-1 overflow-y-auto p-3 sm:p-5 divide-y divide-outline-variant/40 space-y-1">
          {sorted.length === 0 ? (
            <div className="py-16 text-center">
              <span className="material-symbols-outlined text-3xl text-secondary mb-2">find_in_page</span>
              <p className="text-xs text-secondary">
                {isUrdu ? 'کوئی مماثل رپورٹ یا نسخہ نہیں ملا۔' : 'No matching reports or prescriptions found.'}
              </p>
            </div>
          ) : (
            sorted.map((rep) => (
              <ReportCard
                key={rep.id}
                report={rep}
                showDelete={Boolean(onDeleteReport)}
                onDelete={onDeleteReport}
              />
            ))
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-3 border-t border-outline-variant/40 text-[11px] text-secondary text-center bg-surface-container-low/30 shrink-0">
          {isUrdu
            ? 'تمام نتائج کلاؤڈ ڈیٹا بیس سے بلا واسطہ لوڈ کیے گئے ہیں'
            : 'All records loaded directly from your secure health database'}
        </div>
      </div>
    </div>
  );
};
