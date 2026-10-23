import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

export interface ReportItem {
  id: string;
  patient_id: string;
  document_type?: string;
  report_date?: string;
  created_at?: string;
  lab_name?: string;
  doctor_name?: string;
  status: string;
  summary_en?: string;
  summary_ur?: string;
  values?: Array<{
    id?: string;
    test_name: string;
    value?: number;
    flag?: string;
    unit?: string;
  }>;
  medicines?: Array<{
    name: string;
    dosage?: string;
    frequency?: string;
  }>;
}

interface ReportCardProps {
  report: ReportItem;
  onDelete?: (id: string) => void;
  showDelete?: boolean;
}

export const ReportCard: React.FC<ReportCardProps> = ({ report, onDelete, showDelete = false }) => {
  const navigate = useNavigate();
  const { i18n } = useTranslation();
  const isUrdu = i18n.language.startsWith('ur');

  const isPrescription =
    report.document_type === 'prescription' ||
    (report.medicines && report.medicines.length > 0 && (!report.values || report.values.length === 0));

  // Determine date display
  const rawDate = report.report_date || (report.created_at ? report.created_at.slice(0, 10) : '');
  let formattedDate = rawDate;
  if (rawDate) {
    try {
      const d = new Date(rawDate);
      if (!isNaN(d.getTime())) {
        formattedDate = d.toLocaleDateString(isUrdu ? 'ur-PK' : 'en-US', {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
        });
      }
    } catch {
      formattedDate = rawDate;
    }
  }

  // Code-generated status chip and summary line
  let title = '';
  let subtitle = '';
  let chipLabel = '';
  let chipClass = '';
  let summaryText = '';
  let typeIcon = 'lab_profile';

  if (isPrescription) {
    typeIcon = 'prescriptions';
    title = report.doctor_name
      ? (isUrdu ? `ڈاکٹر ${report.doctor_name} کا نسخہ` : `Prescription • Dr. ${report.doctor_name}`)
      : (isUrdu ? "ڈاکٹر کا نسخہ اور ادویات" : "Doctor's Prescription");
    subtitle = report.doctor_name ? `Dr. ${report.doctor_name}` : (isUrdu ? 'کلینک نسخہ' : 'Clinical Prescription');
    const medCount = report.medicines?.length || 0;
    chipLabel = isUrdu ? 'نسخہ' : 'Prescription';
    chipClass = 'bg-primary-container text-on-primary-container';
    if (medCount > 0) {
      summaryText = isUrdu
        ? `${medCount} ادویات: ${report.medicines?.map((m) => m.name).slice(0, 3).join(', ')}`
        : `${medCount} medicines: ${report.medicines?.map((m) => m.name).slice(0, 3).join(', ')}`;
    } else {
      summaryText = isUrdu ? 'ادویات کا نسخہ محفوظ ہے' : 'Prescription details recorded';
    }
  } else {
    typeIcon = 'lab_profile';
    const values = report.values || [];
    const flagged = values.filter((v) => v.flag && v.flag.toLowerCase() !== 'normal');
    const labTitle = report.lab_name
      ? (isUrdu ? `${report.lab_name} لیب رپورٹ` : `${report.lab_name} Lab Report`)
      : (isUrdu ? 'تشخیصی لیب رپورٹ' : 'Diagnostic Lab Report');

    title = labTitle;
    subtitle = report.lab_name || (isUrdu ? 'ڈائیگنوسٹک سینٹر' : 'Diagnostic Center');

    if (flagged.length > 0) {
      const names = flagged.map((v) => `${v.test_name} (${v.flag})`).slice(0, 3).join(', ');
      chipLabel = isUrdu ? 'توجہ طلب' : 'Needs attention';
      chipClass = 'bg-error-container text-on-error-container font-bold';
      summaryText = isUrdu
        ? `${flagged.length} غیر معمولی نتائج: ${names}`
        : `${flagged.length} flagged: ${names}`;
    } else if (values.length > 0) {
      chipLabel = isUrdu ? 'نارمل' : 'Normal';
      chipClass = 'bg-[#DCFCE7] text-[#16A34A] font-bold';
      summaryText = isUrdu
        ? `تمام ${values.length} نتائج نارمل حدود میں ہیں`
        : `All ${values.length} values within normal reference ranges`;
    } else {
      chipLabel = isUrdu ? 'جائزہ درکار ہے' : 'Review needed';
      chipClass = 'bg-surface-container text-secondary font-semibold';
      summaryText = isUrdu
        ? 'رپورٹ محفوظ ہے، مکمل تفصیلات دیکھنے کے لیے کلک کریں۔'
        : 'Report saved, click to view extracted clinical values.';
    }
  }

  const handleCardClick = () => {
    navigate(`/reports/${report.id}`);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleCardClick();
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleCardClick}
      onKeyDown={handleKeyDown}
      className="py-4 px-3 sm:px-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3.5 hover:bg-surface-container-low/60 rounded-2xl transition-all cursor-pointer border border-transparent hover:border-outline-variant/60 focus:outline-none focus:ring-2 focus:ring-primary/40 group"
    >
      <div className="flex items-start gap-3 min-w-0">
        <div className="w-10 h-10 rounded-2xl bg-surface-container text-primary flex items-center justify-center shrink-0 shadow-2xs group-hover:scale-105 transition-transform">
          <span className="material-symbols-outlined text-xl" style={{ fontVariationSettings: "'FILL' 1" }}>
            {typeIcon}
          </span>
        </div>

        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-bold text-on-surface truncate group-hover:text-primary transition-colors">
            {title}
          </h3>
          <div className="flex items-center gap-2 text-xs text-secondary mt-0.5">
            <span className="truncate">{subtitle}</span>
            <span>•</span>
            <span className="shrink-0">{formattedDate}</span>
          </div>
          <p className="text-xs text-on-surface-variant mt-1 line-clamp-1 leading-relaxed">
            {summaryText}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2.5 self-end sm:self-center shrink-0">
        <span className={`text-[10px] px-2.5 py-1 rounded-full uppercase tracking-wider ${chipClass}`}>
          {chipLabel}
        </span>

        <button
          onClick={(e) => {
            e.stopPropagation();
            handleCardClick();
          }}
          className="min-h-[36px] px-3.5 py-1.5 rounded-xl border border-outline-variant/60 hover:border-primary text-xs font-bold text-primary group-hover:bg-primary group-hover:text-on-primary transition-all active:scale-95"
        >
          {isUrdu ? 'تفصیلات دیکھیں' : 'View Details'}
        </button>

        {showDelete && onDelete && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(report.id);
            }}
            className="p-1.5 text-secondary hover:text-error hover:bg-error-container/20 rounded-xl transition-colors"
            title={isUrdu ? 'حذف کریں' : 'Delete Report'}
          >
            <span className="material-symbols-outlined text-base">delete</span>
          </button>
        )}
      </div>
    </div>
  );
};
