import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import api from '../lib/api';
import { useAuth } from '../context/AuthContext';

// ── Types for Lab Reports ────────────────────────────────────────────────────
interface ReportValue {
  id?: string;
  test_name: string;
  canonical_name?: string;
  value?: number;
  raw_value?: string;
  unit?: string;
  ref_low?: number;
  ref_high?: number;
  flag: 'low' | 'normal' | 'high' | 'critical';
  specialty_hint?: string;
  is_user_edited?: boolean;
  sanity_error?: string;
}

interface ReportResult {
  id: string;
  patient_id: string;
  report_date?: string;
  patient_name_found?: string;
  lab_name?: string;
  patient_name_mismatch?: boolean;
  mismatch_warning?: string;
  document_type?: string;
  is_medical_document?: boolean;
  rejection_reason?: string;
  status: string;
  summary_en: string;
  summary_ur: string;
  questions_for_doctor: {
    en: string[];
    ur: string[];
  };
  overall_risk: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  values: ReportValue[];
  recommended_specialty?: string;
}

// ── Types for Doctor Prescriptions ───────────────────────────────────────────
interface PrescribedMedicineItem {
  name: string;
  dosage?: string;
  frequency?: string;
  duration?: string;
  instructions?: string;
  purpose_en?: string;
  purpose_ur?: string;
  allergy_warning?: string;
}

interface PrescriptionResult {
  id: string;
  patient_id: string;
  prescription_date?: string;
  doctor_name?: string;
  patient_name_found?: string;
  patient_name_mismatch?: boolean;
  mismatch_warning?: string;
  document_type?: string;
  is_medical_document?: boolean;
  quality?: string;
  rejection_reason?: string;
  diagnosis_or_notes?: string;
  medicines: PrescribedMedicineItem[];
  general_advice_en?: string;
  general_advice_ur?: string;
  allergy_alerts: string[];
  confidence?: string;
  status: string;
}

interface ReportTranslatePageProps {
  currentPatientId?: string;
}

export const ReportTranslatePage: React.FC<ReportTranslatePageProps> = ({ currentPatientId: propPatientId }) => {
  const { profile } = useAuth();
  const currentPatientId = propPatientId || profile?.id || '';
  const { i18n } = useTranslation();
  const navigate = useNavigate();
  const { reportId: routeReportId } = useParams<{ reportId?: string }>();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Active Section Mode: 'lab' for Diagnostic Test Reports, 'prescription' for Doctor's Prescriptions
  const [activeTab, setActiveTab] = useState<'lab' | 'prescription'>('lab');

  // Common File State
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [loadingSaved, setLoadingSaved] = useState(false);
  const [deletingReport, setDeletingReport] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [analysisStep, setAnalysisStep] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [uploadedReportId, setUploadedReportId] = useState<string | null>(null);

  // Lab Report States
  const [labResult, setLabResult] = useState<ReportResult | null>(null);
  const [editableValues, setEditableValues] = useState<ReportValue[]>([]);
  const [isEditingTable, setIsEditingTable] = useState(false);
  const [confirmingLab, setConfirmingLab] = useState(false);
  const [patientNameAcknowledged, setPatientNameAcknowledged] = useState(false);
  const [confirmSuccessMessage, setConfirmSuccessMessage] = useState<string | null>(null);

  // Prescription States
  const [prescriptionResult, setPrescriptionResult] = useState<PrescriptionResult | null>(null);
  const [editableMedicines, setEditableMedicines] = useState<PrescribedMedicineItem[]>([]);
  const [isEditingMedicines, setIsEditingMedicines] = useState(false);
  const [confirmingPrescription, setConfirmingPrescription] = useState(false);
  const [prescriptionSavedMessage, setPrescriptionSavedMessage] = useState<string | null>(null);

  // Language toggle for bilingual summaries
  const [summaryLangTab, setSummaryLangTab] = useState<'en' | 'ur'>(
    i18n.language.startsWith('ur') ? 'ur' : 'en'
  );

  // Load saved report directly without any LLM call
  useEffect(() => {
    if (!routeReportId) return;

    let isMounted = true;
    const fetchSavedReport = async () => {
      setLoadingSaved(true);
      setError(null);
      try {
        const res = await api.get(`/api/reports/${routeReportId}`);
        const data = res.data;
        if (!isMounted) return;

        setUploadedReportId(data.id);
        const isPrescription =
          data.document_type === 'prescription' ||
          (data.medicines && data.medicines.length > 0);

        if (isPrescription) {
          setActiveTab('prescription');
          setPrescriptionResult({
            id: data.id,
            patient_id: data.patient_id,
            prescription_date: data.report_date,
            doctor_name: data.doctor_name,
            document_type: 'prescription',
            is_medical_document: true,
            diagnosis_or_notes: data.diagnosis_or_notes,
            medicines: data.medicines || [],
            general_advice_en: data.summary_en,
            general_advice_ur: data.summary_ur,
            allergy_alerts: data.allergy_alerts || [],
            confidence: data.confidence,
            status: data.status || 'confirmed',
          });
          setEditableMedicines(data.medicines || []);
        } else {
          setActiveTab('lab');
          setLabResult({
            id: data.id,
            patient_id: data.patient_id,
            report_date: data.report_date,
            lab_name: data.lab_name,
            document_type: data.document_type || 'lab_report',
            is_medical_document: true,
            status: data.status || 'confirmed',
            summary_en: data.summary_en || '',
            summary_ur: data.summary_ur || '',
            questions_for_doctor: data.questions_for_doctor || { en: [], ur: [] },
            overall_risk: data.overall_risk || 'LOW',
            values: data.values || [],
            recommended_specialty: data.recommended_specialty,
          });
          setEditableValues(data.values || []);
        }
      } catch (err: any) {
        if (!isMounted) return;
        console.error('Failed to load saved report:', err);
        setError(err?.response?.data?.detail || 'Failed to load report from database.');
      } finally {
        if (isMounted) setLoadingSaved(false);
      }
    };

    fetchSavedReport();
    return () => {
      isMounted = false;
    };
  }, [routeReportId]);

  const handleDeleteReport = async () => {
    const reportToDelete = routeReportId || uploadedReportId;
    if (!reportToDelete) return;
    setDeletingReport(true);
    try {
      await api.delete(`/api/reports/${reportToDelete}`);
      navigate('/');
    } catch (err: any) {
      console.error('Failed to delete report:', err);
      setError(err?.response?.data?.detail || 'Failed to delete report.');
      setShowDeleteConfirm(false);
    } finally {
      setDeletingReport(false);
    }
  };

  const handleTabSwitch = (newTab: 'lab' | 'prescription') => {
    if (activeTab === newTab) return;
    setActiveTab(newTab);
    resetAll();
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      setError(null);
      if (file.type.startsWith('image/')) {
        setPreviewUrl(URL.createObjectURL(file));
      } else {
        setPreviewUrl(null);
      }
    }
  };

  // ── ANALYSIS DISPATCHER ────────────────────────────────────────────────────
  const handleUploadAndAnalyze = async () => {
    if (!selectedFile) return;

    setAnalyzing(true);
    setError(null);
    setAnalysisStep('Uploading document to secure storage...');

    try {
      const formData = new FormData();
      formData.append('patient_id', currentPatientId);
      formData.append('file', selectedFile);

      // Step 1: Upload file
      const uploadRes = await api.post('/api/reports/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const reportId = uploadRes.data.report_id;
      setUploadedReportId(reportId);

      if (activeTab === 'lab') {
        // Lab Report Analysis Flow
        setAnalysisStep('Preprocessing scan & classifying document...');
        await new Promise((r) => setTimeout(r, 400));

        setAnalysisStep('Extracting lab test values with Gemma 4 Vision...');
        await new Promise((r) => setTimeout(r, 500));

        setAnalysisStep('Validating numbers & calculating clinical flags in code...');
        await new Promise((r) => setTimeout(r, 400));

        setAnalysisStep('Generating plain-language explanation in English and Urdu...');
        const analyzeRes = await api.post(`/api/reports/${reportId}/analyze`);

        setLabResult(analyzeRes.data);
        setEditableValues(analyzeRes.data.values || []);
        setPatientNameAcknowledged(!analyzeRes.data.patient_name_mismatch);
        setIsEditingTable(false);
        setConfirmSuccessMessage(null);
      } else {
        // Doctor Prescription Analysis Flow
        setAnalysisStep('Scanning prescription & reading handwriting...');
        await new Promise((r) => setTimeout(r, 400));

        setAnalysisStep('Extracting medications, dosage, frequency & duration...');
        await new Promise((r) => setTimeout(r, 500));

        setAnalysisStep('Cross-checking medications against recorded patient allergies...');
        await new Promise((r) => setTimeout(r, 400));

        setAnalysisStep('Translating instructions & purpose to English and Urdu...');
        const analyzeRes = await api.post(`/api/reports/${reportId}/analyze-prescription`);

        setPrescriptionResult(analyzeRes.data);
        setEditableMedicines(analyzeRes.data.medicines || []);
        setPatientNameAcknowledged(!analyzeRes.data.patient_name_mismatch);
        setIsEditingMedicines(false);
        setPrescriptionSavedMessage(null);
      }
    } catch (err: any) {
      console.error('Document analysis error:', err);
      const detailMsg =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to process medical document. Please ensure the document is clear and readable, then try again.';
      setError(detailMsg);
      setLabResult(null);
      setPrescriptionResult(null);
    } finally {
      setAnalyzing(false);
    }
  };

  // Switch document type if wrong tab was used
  const handleSwitchAndReanalyze = async (targetTab: 'lab' | 'prescription') => {
    setActiveTab(targetTab);
    if (!uploadedReportId) return;

    setAnalyzing(true);
    setError(null);
    setAnalysisStep(`Switching to ${targetTab === 'lab' ? 'Lab Report' : 'Prescription'} pipeline...`);

    try {
      if (targetTab === 'lab') {
        const analyzeRes = await api.post(`/api/reports/${uploadedReportId}/analyze`);
        setLabResult(analyzeRes.data);
        setEditableValues(analyzeRes.data.values || []);
        setPrescriptionResult(null);
      } else {
        const analyzeRes = await api.post(`/api/reports/${uploadedReportId}/analyze-prescription`);
        setPrescriptionResult(analyzeRes.data);
        setEditableMedicines(analyzeRes.data.medicines || []);
        setLabResult(null);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to analyze under new category.');
    } finally {
      setAnalyzing(false);
    }
  };

  // ── LAB CONFIRMATION ───────────────────────────────────────────────────────
  const handleConfirmLabValues = async () => {
    if (!labResult) return;
    setConfirmingLab(true);
    setConfirmSuccessMessage(null);

    try {
      const payload = {
        values: editableValues.map((v) => ({
          test_name: v.test_name,
          canonical_name: v.canonical_name,
          value: v.value !== undefined && v.value !== null ? Number(v.value) : undefined,
          raw_value: v.raw_value,
          unit: v.unit,
          ref_low: v.ref_low !== undefined && v.ref_low !== null ? Number(v.ref_low) : undefined,
          ref_high: v.ref_high !== undefined && v.ref_high !== null ? Number(v.ref_high) : undefined,
          is_user_edited: v.is_user_edited || false,
        })),
        patient_name_acknowledged: patientNameAcknowledged,
      };

      const res = await api.post(`/api/reports/${labResult.id}/confirm`, payload);
      setLabResult(res.data);
      setEditableValues(res.data.values || []);
      setIsEditingTable(false);
      setConfirmSuccessMessage('Lab flags and clinical explanation recalculated from your confirmed values.');
    } catch (err: any) {
      console.error('Confirmation error:', err);
      setError('Failed to confirm report values. Please try again.');
    } finally {
      setConfirmingLab(false);
    }
  };

  // ── PRESCRIPTION CONFIRMATION & MEMORY PERSISTENCE ─────────────────────────
  const handleConfirmPrescription = async () => {
    if (!prescriptionResult) return;
    setConfirmingPrescription(true);
    setPrescriptionSavedMessage(null);

    try {
      const payload = {
        medicines: editableMedicines,
        diagnosis_or_notes: prescriptionResult.diagnosis_or_notes,
        patient_name_acknowledged: patientNameAcknowledged,
        save_to_memory: true,
      };

      const res = await api.post(`/api/reports/${prescriptionResult.id}/confirm-prescription`, payload);
      setPrescriptionResult(res.data);
      setEditableMedicines(res.data.medicines || []);
      setIsEditingMedicines(false);
      setPrescriptionSavedMessage(
        'Prescription saved! These medications are now safely recorded in your health profile and remembered by your AI Doctor across all future chats.'
      );
    } catch (err: any) {
      console.error('Prescription confirmation error:', err);
      setError('Failed to save prescription. Please try again.');
    } finally {
      setConfirmingPrescription(false);
    }
  };

  const resetAll = () => {
    setSelectedFile(null);
    setPreviewUrl(null);
    setLabResult(null);
    setPrescriptionResult(null);
    setError(null);
    setUploadedReportId(null);
    setEditableValues([]);
    setIsEditingTable(false);
    setEditableMedicines([]);
    setIsEditingMedicines(false);
    setConfirmSuccessMessage(null);
    setPrescriptionSavedMessage(null);
  };

  const getFlagBadge = (flag: string) => {
    switch (flag) {
      case 'critical':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#FEE2E2] text-[#DC2626] border border-[#DC2626]/20">
            CRITICAL
          </span>
        );
      case 'high':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#FEF3C7] text-[#D97706] border border-[#D97706]/20">
            HIGH
          </span>
        );
      case 'low':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#DBEAFE] text-[#2563EB] border border-[#2563EB]/20">
            LOW
          </span>
        );
      case 'normal':
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#DCFCE7] text-[#16A34A] border border-[#16A34A]/20">
            NORMAL
          </span>
        );
    }
  };

  const getRiskBadge = (risk: string) => {
    switch (risk) {
      case 'CRITICAL':
        return (
          <span className="bg-error text-on-error text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider">
            Urgent Attention
          </span>
        );
      case 'HIGH':
        return (
          <span className="bg-[#D97706] text-white text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider">
            High Risk
          </span>
        );
      case 'MEDIUM':
        return (
          <span className="bg-[#B45309] text-white text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider">
            Moderate Attention
          </span>
        );
      default:
        return (
          <span className="bg-[#16A34A] text-white text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider">
            Healthy Status
          </span>
        );
    }
  };

  const currentResult = activeTab === 'lab' ? labResult : prescriptionResult;

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-4 md:py-6 space-y-5">
      {/* ── HEADER ────────────────────────────────────────────────────────── */}
      <div className="text-center max-w-2xl mx-auto">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-container text-primary text-xs font-bold mb-2 border border-outline-variant/50">
          <span
            className="material-symbols-outlined text-sm text-primary"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            verified_user
          </span>
          <span>Dual-Category Verification • Clinical Code Guardrails • Cross-Chat Memory</span>
        </div>
        <h1 className="text-2xl md:text-3xl font-extrabold text-on-surface tracking-tight">
          Medical Documents & Analysis
        </h1>
        <p className="mt-1.5 text-xs md:text-sm text-secondary">
          Upload diagnostic lab tests or doctor prescriptions into their dedicated sections. Everything is cross-verified and remembered by your AI Doctor.
        </p>

        {/* ── SECTION SWITCHER (Tabs) ────────────────────────────────────────── */}
        {!routeReportId && (
          <div className="mt-4 inline-flex p-1 rounded-2xl bg-surface-container-low border border-outline-variant/70 shadow-xs">
            <button
              onClick={() => handleTabSwitch('lab')}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl font-bold text-xs md:text-sm transition-all ${
                activeTab === 'lab'
                  ? 'bg-primary-container text-on-primary-container shadow-xs scale-102'
                  : 'text-secondary hover:text-on-surface'
              }`}
            >
              <span className="material-symbols-outlined text-base">science</span>
              <span>🧪 Diagnostic Lab Report</span>
            </button>

            <button
              onClick={() => handleTabSwitch('prescription')}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl font-bold text-xs md:text-sm transition-all ${
                activeTab === 'prescription'
                  ? 'bg-primary-container text-on-primary-container shadow-xs scale-102'
                  : 'text-secondary hover:text-on-surface'
              }`}
            >
              <span className="material-symbols-outlined text-base">prescriptions</span>
              <span>💊 Doctor's Prescription</span>
            </button>
          </div>
        )}

        {/* Back button when viewing a saved report */}
        {routeReportId && (
          <div className="mt-4 flex items-center justify-between">
            <button
              type="button"
              onClick={() => navigate('/')}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-outline-variant/60 hover:bg-surface-container-low text-xs font-semibold text-secondary hover:text-on-surface transition-colors cursor-pointer"
            >
              <span className="material-symbols-outlined text-base">arrow_back</span>
              <span>Back to Home</span>
            </button>

            <button
              type="button"
              onClick={() => setShowDeleteConfirm(true)}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl border border-error/30 hover:bg-error/10 text-xs font-semibold text-error transition-colors cursor-pointer"
            >
              <span className="material-symbols-outlined text-sm">delete</span>
              <span>Delete Report</span>
            </button>
          </div>
        )}
      </div>

      {/* Top-Level Error Banner when opening a report */}
      {error && (
        <div className="bg-error-container text-on-error-container p-4 rounded-2xl text-xs flex items-center justify-between max-w-2xl mx-auto shadow-xs">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-base">error</span>
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="font-bold underline cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading Saved Report Indicator */}
      {loadingSaved && (
        <div className="bg-surface-container-lowest rounded-3xl border border-outline-variant/60 shadow-xs p-10 max-w-2xl mx-auto text-center space-y-3">
          <div className="w-12 h-12 mx-auto rounded-2xl bg-surface-container flex items-center justify-center text-primary animate-spin">
            <span className="material-symbols-outlined text-2xl">sync</span>
          </div>
          <p className="text-sm font-bold text-on-surface">Loading saved record from database...</p>
          <p className="text-xs text-secondary">Zero AI calls triggered.</p>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in">
          <div className="bg-surface-container-lowest rounded-3xl border border-outline-variant/60 shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-error-container text-on-error-container flex items-center justify-center">
              <span className="material-symbols-outlined text-2xl">delete_forever</span>
            </div>
            <div>
              <h3 className="text-base font-bold text-on-surface">Delete this report?</h3>
              <p className="text-xs text-secondary mt-1">
                This will permanently remove the report, its extracted clinical values, and stored files. This cannot be undone.
              </p>
            </div>
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(false)}
                className="px-4 py-2 rounded-xl text-xs font-bold text-secondary hover:text-on-surface transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={deletingReport}
                onClick={handleDeleteReport}
                className="px-4 py-2 rounded-xl text-xs font-bold bg-error text-on-error hover:bg-error/90 transition-colors cursor-pointer"
              >
                {deletingReport ? 'Deleting...' : 'Yes, Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── UPLOAD DROPZONE ────────────────────────────────────────────────── */}
      {!loadingSaved && !currentResult && (
        <div className="bg-surface-container-lowest rounded-3xl border border-outline-variant/60 shadow-xs p-5 md:p-6 max-w-2xl mx-auto">
          <div
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-3xl p-6 text-center cursor-pointer transition-all ${
              selectedFile
                ? 'border-primary bg-primary-container/5'
                : 'border-outline-variant hover:border-primary hover:bg-surface-container-low/50'
            }`}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileSelect}
              accept="image/*,.pdf"
              className="hidden"
            />

            {previewUrl ? (
              <div className="flex flex-col items-center">
                <img
                  src={previewUrl}
                  alt="Document Preview"
                  className="max-h-48 rounded-2xl object-contain shadow-xs mb-3 border border-outline-variant"
                />
                <p className="text-xs font-bold text-primary flex items-center gap-1">
                  <span className="material-symbols-outlined text-base">check_circle</span>
                  <span>{selectedFile?.name}</span>
                </p>
              </div>
            ) : selectedFile ? (
              <div className="flex flex-col items-center py-4">
                <div className="w-16 h-16 rounded-2xl bg-primary-container text-on-primary-container flex items-center justify-center mb-3 shadow-xs">
                  <span className="material-symbols-outlined text-3xl">description</span>
                </div>
                <p className="font-bold text-on-surface text-sm">{selectedFile.name}</p>
                <p className="text-xs text-secondary mt-1">
                  {(selectedFile.size / 1024 / 1024).toFixed(2)} MB • Ready for analysis
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center py-6">
                <div className="w-16 h-16 rounded-2xl bg-surface-container text-primary flex items-center justify-center mb-3 shadow-xs">
                  <span
                    className="material-symbols-outlined text-3xl"
                    style={{ fontVariationSettings: "'FILL' 1" }}
                  >
                    {activeTab === 'lab' ? 'cloud_upload' : 'medication'}
                  </span>
                </div>
                <p className="font-bold text-on-surface text-base">
                  {activeTab === 'lab'
                    ? 'Upload lab report photo or PDF'
                    : "Upload doctor's prescription photo or PDF"}
                </p>
                <p className="text-xs text-secondary mt-1 max-w-sm">
                  {activeTab === 'lab'
                    ? 'CBC, Fasting Blood Sugar, Lipid Profile, LFT, RFT, Urine analysis'
                    : 'Handwritten slips, printed clinic prescriptions, discharge medicine lists'}
                </p>
              </div>
            )}
          </div>

          {error && (
            <div className="mt-4 p-3 bg-error-container text-on-error-container rounded-2xl text-xs flex items-center gap-2">
              <span className="material-symbols-outlined text-base">error</span>
              <span>{error}</span>
            </div>
          )}

          {/* Action Trigger */}
          <div className="mt-6 flex flex-col gap-3">
            <button
              disabled={!selectedFile || analyzing}
              onClick={handleUploadAndAnalyze}
              className={`w-full py-3.5 px-6 rounded-2xl font-bold text-xs md:text-sm shadow-xs transition-all flex items-center justify-center gap-2 ${
                !selectedFile || analyzing
                  ? 'bg-surface-container text-secondary cursor-not-allowed'
                  : 'bg-primary-container hover:opacity-95 text-on-primary-container active:scale-98'
              }`}
            >
              {analyzing ? (
                <>
                  <span className="material-symbols-outlined text-lg animate-spin">
                    progress_activity
                  </span>
                  <span>{analysisStep}</span>
                </>
              ) : (
                <>
                  <span
                    className="material-symbols-outlined text-lg"
                    style={{ fontVariationSettings: "'FILL' 1" }}
                  >
                    auto_awesome
                  </span>
                  <span>
                    {activeTab === 'lab' ? 'Analyze Lab Report' : 'Analyze Prescription'}
                  </span>
                </>
              )}
            </button>

            {analyzing && (
              <div className="bg-surface-container-low border border-outline-variant/60 rounded-2xl p-3 text-xs text-secondary text-center animate-pulse">
                <span>{analysisStep}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── REJECTION VIEW (Document Classifier Guardrail) ────────────────────── */}
      {currentResult && (!currentResult.is_medical_document || currentResult.status === 'rejected') && (
        <div className="bg-surface-container-lowest rounded-3xl border border-error/30 shadow-xs p-6 md:p-10 max-w-2xl mx-auto text-center space-y-4">
          <div className="w-16 h-16 mx-auto rounded-2xl bg-error-container text-on-error-container flex items-center justify-center shadow-xs">
            <span className="material-symbols-outlined text-3xl">document_scanner</span>
          </div>
          <h2 className="text-xl md:text-2xl font-bold text-on-surface">
            Non-Medical or Unreadable Document
          </h2>
          <p className="text-xs md:text-sm text-secondary leading-relaxed max-w-md mx-auto">
            {currentResult.rejection_reason ||
              'The uploaded document does not appear to be a valid medical document. Please upload a clear photo or PDF.'}
          </p>
          <div className="pt-4">
            <button
              onClick={resetAll}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-2xl bg-primary text-on-primary font-bold text-xs shadow-xs hover:opacity-95 transition-all"
            >
              <span className="material-symbols-outlined text-base">cloud_upload</span>
              <span>Upload a Valid Medical Document</span>
            </button>
          </div>
        </div>
      )}

      {/* ── CROSS-SECTION DETECTION HINT (Prescription uploaded in Lab tab) ─────── */}
      {labResult && labResult.document_type === 'prescription' && (
        <div className="bg-[#EFF6FF] border border-[#3B82F6]/40 rounded-3xl p-5 shadow-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <span className="material-symbols-outlined text-[#2563EB] text-2xl shrink-0 mt-0.5">
              prescriptions
            </span>
            <div>
              <h4 className="font-bold text-sm text-[#1E3A8A]">
                Doctor's Prescription Detected in Lab Section
              </h4>
              <p className="text-xs text-[#1D4ED8] mt-0.5 leading-relaxed">
                This document was identified as a doctor's prescription rather than a lab test. Switch to the Prescription tab to parse medicine names, dosages, and verify against your allergies.
              </p>
            </div>
          </div>
          <button
            onClick={() => handleSwitchAndReanalyze('prescription')}
            className="shrink-0 px-4 py-2 rounded-xl bg-[#2563EB] text-white font-bold text-xs shadow-xs hover:bg-[#1D4ED8] transition-all"
          >
            Switch to Prescription Tab
          </button>
        </div>
      )}

      {/* ── CROSS-SECTION DETECTION HINT (Lab Report uploaded in Prescription tab) ── */}
      {prescriptionResult && prescriptionResult.document_type === 'lab_report' && (
        <div className="bg-[#EFF6FF] border border-[#3B82F6]/40 rounded-3xl p-5 shadow-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <span className="material-symbols-outlined text-[#2563EB] text-2xl shrink-0 mt-0.5">
              science
            </span>
            <div>
              <h4 className="font-bold text-sm text-[#1E3A8A]">
                Diagnostic Lab Report Detected in Prescription Section
              </h4>
              <p className="text-xs text-[#1D4ED8] mt-0.5 leading-relaxed">
                This document was identified as a diagnostic lab report. Switch to the Lab Report tab to inspect numerical test values and reference flags.
              </p>
            </div>
          </div>
          <button
            onClick={() => handleSwitchAndReanalyze('lab')}
            className="shrink-0 px-4 py-2 rounded-xl bg-[#2563EB] text-white font-bold text-xs shadow-xs hover:bg-[#1D4ED8] transition-all"
          >
            Switch to Lab Report Tab
          </button>
        </div>
      )}

      {/* ── 1. LAB REPORT RESULT VIEW ────────────────────────────────────────── */}
      {activeTab === 'lab' && labResult && labResult.is_medical_document && labResult.status !== 'rejected' && (
        <div className="space-y-6 animate-in fade-in duration-300">
          {/* Patient Name Mismatch Warning Banner */}
          {labResult.patient_name_mismatch && (
            <div className="bg-[#FEF3C7] border border-[#D97706]/40 rounded-3xl p-5 shadow-xs flex items-start gap-3.5">
              <span className="material-symbols-outlined text-[#D97706] text-2xl shrink-0 mt-0.5">
                warning
              </span>
              <div className="flex-1 text-xs md:text-sm text-[#92400E]">
                <h4 className="font-bold text-sm md:text-base text-[#78350F]">
                  Patient Name Mismatch Detected
                </h4>
                <p className="mt-1 leading-relaxed">
                  {labResult.mismatch_warning ||
                    `The report shows the patient name '${labResult.patient_name_found}', which does not match your active profile name ('${profile?.full_name || 'Self'}').`}
                </p>
                <label className="flex items-center gap-2.5 mt-3 font-semibold cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={patientNameAcknowledged}
                    onChange={(e) => setPatientNameAcknowledged(e.target.checked)}
                    className="w-4 h-4 rounded border-[#D97706] text-primary focus:ring-primary cursor-pointer"
                  />
                  <span>I confirm this report belongs to me or was uploaded on my behalf</span>
                </label>
              </div>
            </div>
          )}

          {/* Success Banner on Recalculation */}
          {confirmSuccessMessage && (
            <div className="bg-[#DCFCE7] border border-[#16A34A]/30 rounded-2xl p-4 text-xs md:text-sm text-[#166534] flex items-center justify-between gap-3 shadow-xs">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-base">check_circle</span>
                <span>{confirmSuccessMessage}</span>
              </div>
              <button
                onClick={() => setConfirmSuccessMessage(null)}
                className="text-[#166534] hover:opacity-75 font-bold text-xs"
              >
                ✕
              </button>
            </div>
          )}

          {/* Top Result Banner */}
          <div className="bg-surface-container-lowest rounded-3xl border border-outline-variant/60 shadow-xs p-6 md:p-8">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 border-b border-outline-variant/40">
              <div>
                <div className="flex items-center gap-3 flex-wrap">
                  <h2 className="text-xl md:text-2xl font-bold text-on-surface">
                    Lab Report Analysis Summary
                  </h2>
                  {getRiskBadge(labResult.overall_risk)}
                </div>
                <p className="text-xs text-secondary mt-1">
                  Report Date: {labResult.report_date || 'Recent'} • Lab: {labResult.lab_name || 'Standard Laboratory'} • Flags computed strictly in Python code
                </p>
              </div>

              <button
                onClick={resetAll}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-surface-container hover:bg-surface-container-high text-xs font-semibold text-on-surface transition-colors"
              >
                <span className="material-symbols-outlined text-base">refresh</span>
                <span>Upload Another</span>
              </button>
            </div>

            {/* Explanation Section */}
            <div className="mt-6">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-bold text-secondary uppercase tracking-wider">
                  Plain-Language Explanation
                </span>
                <div className="flex rounded-xl bg-surface-container p-0.5 border border-outline-variant/50 text-xs font-semibold">
                  <button
                    onClick={() => setSummaryLangTab('en')}
                    className={`px-3 py-1 rounded-lg transition-all ${
                      summaryLangTab === 'en'
                        ? 'bg-surface text-primary shadow-xs'
                        : 'text-secondary hover:text-on-surface'
                    }`}
                  >
                    English
                  </button>
                  <button
                    onClick={() => setSummaryLangTab('ur')}
                    className={`px-3 py-1 rounded-lg transition-all ${
                      summaryLangTab === 'ur'
                        ? 'bg-surface text-primary shadow-xs'
                        : 'text-secondary hover:text-on-surface'
                    }`}
                  >
                    اردو
                  </button>
                </div>
              </div>

              {summaryLangTab === 'en' ? (
                <p className="text-xs md:text-sm text-on-surface leading-relaxed whitespace-pre-line bg-surface-container-low/50 p-4 rounded-2xl border border-outline-variant/30">
                  {labResult.summary_en}
                </p>
              ) : (
                <p
                  dir="rtl"
                  className="text-sm md:text-base font-urdu text-on-surface leading-relaxed whitespace-pre-line bg-surface-container-low/50 p-4 rounded-2xl border border-outline-variant/30"
                >
                  {labResult.summary_ur}
                </p>
              )}
            </div>

            {/* Recommended Specialty Callout */}
            {labResult.recommended_specialty && (
              <div className="mt-4 p-3.5 rounded-2xl bg-primary-container/10 border border-primary/20 flex items-center justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-2.5">
                  <span className="material-symbols-outlined text-primary text-xl">medical_services</span>
                  <span className="text-xs font-bold text-on-surface">
                    Recommended Specialist: <span className="text-primary">{labResult.recommended_specialty}</span>
                  </span>
                </div>
                <button
                  onClick={() => navigate('/doctors')}
                  className="px-3 py-1.5 rounded-xl bg-primary text-on-primary font-bold text-xs hover:opacity-95 transition-all"
                >
                  Find Nearby Specialists
                </button>
              </div>
            )}
          </div>

          {/* Interactive Review Table */}
          <div className="bg-surface-container-lowest rounded-3xl border border-outline-variant/60 shadow-xs p-6 md:p-8">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-4">
              <div>
                <h3 className="font-bold text-on-surface text-base md:text-lg">
                  Lab Test Results & Code Flags
                </h3>
                <p className="text-xs text-secondary mt-0.5">
                  Review extracted test values. Click any field to correct OCR mistakes and re-run safety flags.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setIsEditingTable(!isEditingTable)}
                  className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
                    isEditingTable
                      ? 'bg-primary text-on-primary'
                      : 'bg-surface-container text-on-surface hover:bg-surface-container-high'
                  }`}
                >
                  <span className="material-symbols-outlined text-base">
                    {isEditingTable ? 'done' : 'edit'}
                  </span>
                  <span>{isEditingTable ? 'Done Editing' : 'Edit Values'}</span>
                </button>
              </div>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-outline-variant/60 text-[11px] font-bold text-secondary uppercase tracking-wider">
                    <th className="py-2.5 px-3">Test Name</th>
                    <th className="py-2.5 px-3">Measured Value</th>
                    <th className="py-2.5 px-3">Unit</th>
                    <th className="py-2.5 px-3">Reference Range</th>
                    <th className="py-2.5 px-3">Flag</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-outline-variant/30">
                  {editableValues.map((v, i) => (
                    <tr key={i} className="hover:bg-surface-container-low/30 transition-colors">
                      <td className="py-3 px-3 text-xs font-semibold text-on-surface">
                        {v.test_name}
                      </td>
                      <td className="py-3 px-3 text-xs font-bold text-on-surface">
                        {isEditingTable ? (
                          <input
                            type="number"
                            step="any"
                            value={v.value !== undefined ? v.value : ''}
                            onChange={(e) => {
                              const val = e.target.value === '' ? undefined : parseFloat(e.target.value);
                              setEditableValues((prev) => {
                                const next = [...prev];
                                next[i] = { ...next[i], value: val, is_user_edited: true };
                                return next;
                              });
                            }}
                            className="w-20 p-1.5 text-xs rounded-lg border border-outline-variant bg-surface-container-lowest"
                          />
                        ) : (
                          v.value ?? v.raw_value ?? '—'
                        )}
                      </td>
                      <td className="py-3 px-3 text-xs text-secondary">{v.unit || '—'}</td>
                      <td className="py-3 px-3 text-xs text-secondary">
                        {v.ref_low !== undefined && v.ref_high !== undefined
                          ? `${v.ref_low} – ${v.ref_high}`
                          : v.ref_high
                          ? `< ${v.ref_high}`
                          : 'Standard'}
                      </td>
                      <td className="py-3 px-3">{getFlagBadge(v.flag)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Recalculate Button */}
            <div className="mt-6 pt-4 border-t border-outline-variant/40 flex flex-col sm:flex-row items-center justify-between gap-3">
              <span className="text-xs text-secondary">
                {editableValues.some((v) => v.is_user_edited)
                  ? '⚠️ Unsaved edits detected. Confirm below to recalculate flags.'
                  : 'All values verified against reference ranges.'}
              </span>
              <button
                disabled={confirmingLab}
                onClick={handleConfirmLabValues}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold text-xs bg-primary text-on-primary hover:opacity-95 shadow-xs transition-all"
              >
                {confirmingLab ? 'Recalculating...' : 'Confirm & Recalculate Explanation'}
              </button>
            </div>
          </div>

          {/* Questions for Doctor */}
          <div className="bg-surface-container-lowest rounded-3xl border border-outline-variant/60 shadow-xs p-6 md:p-8">
            <h3 className="font-bold text-on-surface text-base md:text-lg mb-1 flex items-center gap-2">
              <span className="material-symbols-outlined text-primary text-xl">contact_support</span>
              <span>Questions to Ask Your Doctor</span>
            </h3>
            <p className="text-xs text-secondary mb-4">
              Bring these practical questions to your medical appointment.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2.5">
                <span className="text-[10px] font-bold text-secondary uppercase tracking-wider block">
                  In English
                </span>
                {labResult.questions_for_doctor?.en?.map((q, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-2.5 p-3 rounded-2xl bg-surface-container-low border border-outline-variant/50 text-xs text-on-surface"
                  >
                    <span className="material-symbols-outlined text-primary text-base shrink-0 mt-0.5">
                      check_circle
                    </span>
                    <span>{q}</span>
                  </div>
                ))}
              </div>
              <div className="space-y-2.5">
                <span className="text-[10px] font-bold text-secondary uppercase tracking-wider block">
                  اردو میں
                </span>
                {labResult.questions_for_doctor?.ur?.map((q, idx) => (
                  <div
                    key={idx}
                    dir="rtl"
                    className="flex items-start gap-2.5 p-3 rounded-2xl bg-surface-container-low border border-outline-variant/50 text-xs text-on-surface font-urdu leading-relaxed"
                  >
                    <span className="material-symbols-outlined text-primary text-base shrink-0 mt-0.5">
                      check_circle
                    </span>
                    <span>{q}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── 2. DOCTOR PRESCRIPTION RESULT VIEW ───────────────────────────────── */}
      {activeTab === 'prescription' && prescriptionResult && prescriptionResult.is_medical_document && prescriptionResult.status !== 'rejected' && (
        <div className="space-y-6 animate-in fade-in duration-300">
          {/* Patient Name Mismatch Warning Banner */}
          {prescriptionResult.patient_name_mismatch && (
            <div className="bg-[#FEF3C7] border border-[#D97706]/40 rounded-3xl p-5 shadow-xs flex items-start gap-3.5">
              <span className="material-symbols-outlined text-[#D97706] text-2xl shrink-0 mt-0.5">
                warning
              </span>
              <div className="flex-1 text-xs md:text-sm text-[#92400E]">
                <h4 className="font-bold text-sm md:text-base text-[#78350F]">
                  Patient Name Mismatch on Prescription
                </h4>
                <p className="mt-1 leading-relaxed">
                  {prescriptionResult.mismatch_warning ||
                    `The prescription shows patient '${prescriptionResult.patient_name_found}', differing from your profile name ('${profile?.full_name || 'Self'}').`}
                </p>
                <label className="flex items-center gap-2.5 mt-3 font-semibold cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={patientNameAcknowledged}
                    onChange={(e) => setPatientNameAcknowledged(e.target.checked)}
                    className="w-4 h-4 rounded border-[#D97706] text-primary focus:ring-primary cursor-pointer"
                  />
                  <span>I confirm this prescription belongs to me or was prescribed for my care</span>
                </label>
              </div>
            </div>
          )}

          {/* 🚨 ALLERGY SAFETY ALERT BANNER (High Visibility Red Card) 🚨 */}
          {prescriptionResult.allergy_alerts && prescriptionResult.allergy_alerts.length > 0 && (
            <div className="bg-[#FEE2E2] border-2 border-[#DC2626] rounded-3xl p-6 shadow-sm flex items-start gap-4">
              <div className="w-12 h-12 rounded-2xl bg-[#DC2626] text-white flex items-center justify-center shrink-0 shadow-xs">
                <span className="material-symbols-outlined text-2xl">emergency</span>
              </div>
              <div className="flex-1 text-xs md:text-sm text-[#7F1D1D]">
                <h3 className="font-extrabold text-base md:text-lg text-[#991B1B] flex items-center gap-2">
                  <span>CRITICAL MEDICATION ALLERGY WARNING</span>
                </h3>
                <p className="mt-1 text-xs text-[#991B1B]/90 font-medium">
                  One or more prescribed drugs conflict directly with your recorded allergy history. Do not consume these medications without physician clearance:
                </p>
                <ul className="mt-3 space-y-1.5 list-disc list-inside font-bold text-xs md:text-sm text-[#7F1D1D]">
                  {prescriptionResult.allergy_alerts.map((alert, idx) => (
                    <li key={idx} className="leading-relaxed">
                      {alert}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* Success Banner on Saving to Memory */}
          {prescriptionSavedMessage && (
            <div className="bg-[#DCFCE7] border border-[#16A34A]/30 rounded-2xl p-4 text-xs md:text-sm text-[#166534] flex items-center justify-between gap-3 shadow-xs">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-base">check_circle</span>
                <span>{prescriptionSavedMessage}</span>
              </div>
              <button
                onClick={() => setPrescriptionSavedMessage(null)}
                className="text-[#166534] hover:opacity-75 font-bold text-xs"
              >
                ✕
              </button>
            </div>
          )}

          {/* Header Summary Card */}
          <div className="bg-surface-container-lowest rounded-3xl border border-outline-variant/60 shadow-xs p-6 md:p-8">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 border-b border-outline-variant/40">
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="text-xl md:text-2xl font-bold text-on-surface">
                    Doctor's Prescription Summary
                  </h2>
                  <span className="bg-primary text-on-primary text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider">
                    {prescriptionResult.medicines.length} Medication{prescriptionResult.medicines.length === 1 ? '' : 's'}
                  </span>
                </div>
                <p className="text-xs text-secondary mt-1">
                  Doctor / Clinic: <span className="font-semibold text-on-surface">{prescriptionResult.doctor_name || 'Attending Physician'}</span> • Date: <span className="font-semibold text-on-surface">{prescriptionResult.prescription_date || 'Recent'}</span>
                </p>
                {prescriptionResult.diagnosis_or_notes && (
                  <p className="text-xs text-primary font-medium mt-1">
                    Clinical Diagnosis / Remarks: {prescriptionResult.diagnosis_or_notes}
                  </p>
                )}
              </div>

              <button
                onClick={resetAll}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-surface-container hover:bg-surface-container-high text-xs font-semibold text-on-surface transition-colors"
              >
                <span className="material-symbols-outlined text-base">refresh</span>
                <span>Upload Another</span>
              </button>
            </div>

            {/* General Advice */}
            {(prescriptionResult.general_advice_en || prescriptionResult.general_advice_ur) && (
              <div className="mt-6">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-bold text-secondary uppercase tracking-wider">
                    Doctor's General Advice & Precautions
                  </span>
                  <div className="flex rounded-xl bg-surface-container p-0.5 border border-outline-variant/50 text-xs font-semibold">
                    <button
                      onClick={() => setSummaryLangTab('en')}
                      className={`px-3 py-1 rounded-lg transition-all ${
                        summaryLangTab === 'en'
                          ? 'bg-surface text-primary shadow-xs'
                          : 'text-secondary hover:text-on-surface'
                      }`}
                    >
                      English
                    </button>
                    <button
                      onClick={() => setSummaryLangTab('ur')}
                      className={`px-3 py-1 rounded-lg transition-all ${
                        summaryLangTab === 'ur'
                          ? 'bg-surface text-primary shadow-xs'
                          : 'text-secondary hover:text-on-surface'
                      }`}
                    >
                      اردو
                    </button>
                  </div>
                </div>

                {summaryLangTab === 'en' ? (
                  <p className="text-xs md:text-sm text-on-surface leading-relaxed whitespace-pre-line bg-surface-container-low/50 p-4 rounded-2xl border border-outline-variant/30">
                    {prescriptionResult.general_advice_en || 'Take medications exactly as prescribed with plenty of water.'}
                  </p>
                ) : (
                  <p
                    dir="rtl"
                    className="text-sm md:text-base font-urdu text-on-surface leading-relaxed whitespace-pre-line bg-surface-container-low/50 p-4 rounded-2xl border border-outline-variant/30"
                  >
                    {prescriptionResult.general_advice_ur || 'ادویات ڈاکٹر کی ہدایت کے مطابق وقت پر اور مناسب پانی کے ساتھ لیں۔'}
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Prescribed Medications Card Grid */}
          <div className="bg-surface-container-lowest rounded-3xl border border-outline-variant/60 shadow-xs p-6 md:p-8">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
              <div>
                <h3 className="font-bold text-on-surface text-base md:text-lg flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary text-xl">medication</span>
                  <span>Prescribed Medications & Dosage Schedule</span>
                </h3>
                <p className="text-xs text-secondary mt-0.5">
                  Extracted from doctor's slip with Urdu explanations and safety checks.
                </p>
              </div>

              <button
                onClick={() => setIsEditingMedicines(!isEditingMedicines)}
                className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
                  isEditingMedicines
                    ? 'bg-primary text-on-primary'
                    : 'bg-surface-container text-on-surface hover:bg-surface-container-high'
                }`}
              >
                <span className="material-symbols-outlined text-base">
                  {isEditingMedicines ? 'done' : 'edit'}
                </span>
                <span>{isEditingMedicines ? 'Done Editing' : 'Edit Medications'}</span>
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {editableMedicines.map((med, idx) => {
                const hasAllergyWarning = Boolean(med.allergy_warning);
                return (
                  <div
                    key={idx}
                    className={`p-5 rounded-2xl border transition-all ${
                      hasAllergyWarning
                        ? 'bg-[#FEF2F2] border-[#DC2626]/40 shadow-xs'
                        : 'bg-surface-container-low/60 border-outline-variant/60'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        {isEditingMedicines ? (
                          <input
                            type="text"
                            value={med.name}
                            onChange={(e) => {
                              const val = e.target.value;
                              setEditableMedicines((prev) => {
                                const next = [...prev];
                                next[idx] = { ...next[idx], name: val };
                                return next;
                              });
                            }}
                            className="font-bold text-sm text-on-surface p-1 rounded-lg border border-outline-variant bg-surface-container-lowest"
                          />
                        ) : (
                          <h4 className="font-bold text-base text-on-surface flex items-center gap-1.5">
                            <span>{med.name}</span>
                            {med.dosage && (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-primary-container text-on-primary-container font-semibold">
                                {med.dosage}
                              </span>
                            )}
                          </h4>
                        )}
                        {hasAllergyWarning && (
                          <span className="mt-1 inline-flex items-center gap-1 text-[11px] font-bold text-[#DC2626]">
                            <span className="material-symbols-outlined text-xs">warning</span>
                            <span>Allergy Conflict</span>
                          </span>
                        )}
                      </div>

                      {hasAllergyWarning ? (
                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold bg-[#FEE2E2] text-[#DC2626] border border-[#DC2626]/30">
                          CONFLICT
                        </span>
                      ) : (
                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-[#DCFCE7] text-[#16A34A] border border-[#16A34A]/20">
                          ALLERGY SAFE
                        </span>
                      )}
                    </div>

                    {/* Dosage Details */}
                    <div className="mt-3.5 space-y-1.5 text-xs">
                      <div className="flex items-center gap-2 text-secondary">
                        <span className="material-symbols-outlined text-sm text-primary">schedule</span>
                        <span className="font-semibold text-on-surface">Frequency:</span>
                        {isEditingMedicines ? (
                          <input
                            type="text"
                            value={med.frequency || ''}
                            onChange={(e) => {
                              const val = e.target.value;
                              setEditableMedicines((prev) => {
                                const next = [...prev];
                                next[idx] = { ...next[idx], frequency: val };
                                return next;
                              });
                            }}
                            placeholder="e.g. Twice daily"
                            className="p-1 rounded-lg border border-outline-variant text-xs bg-surface-container-lowest"
                          />
                        ) : (
                          <span>{med.frequency || 'As directed'}</span>
                        )}
                      </div>

                      {med.duration && (
                        <div className="flex items-center gap-2 text-secondary">
                          <span className="material-symbols-outlined text-sm text-primary">hourglass_bottom</span>
                          <span className="font-semibold text-on-surface">Duration:</span>
                          <span>{med.duration}</span>
                        </div>
                      )}

                      {med.instructions && (
                        <div className="flex items-center gap-2 text-secondary">
                          <span className="material-symbols-outlined text-sm text-primary">restaurant</span>
                          <span className="font-semibold text-on-surface">Timing:</span>
                          <span>{med.instructions}</span>
                        </div>
                      )}
                    </div>

                    {/* Purpose in English and Urdu */}
                    {(med.purpose_en || med.purpose_ur) && (
                      <div className="mt-3 pt-3 border-t border-outline-variant/40 space-y-1">
                        {med.purpose_en && (
                          <p className="text-xs text-secondary">
                            <span className="font-semibold text-on-surface">Purpose: </span>
                            {med.purpose_en}
                          </p>
                        )}
                        {med.purpose_ur && (
                          <p dir="rtl" className="text-xs font-urdu text-secondary leading-relaxed">
                            <span className="font-semibold text-on-surface">مقصد: </span>
                            {med.purpose_ur}
                          </p>
                        )}
                      </div>
                    )}

                    {/* Allergy warning specific note */}
                    {med.allergy_warning && (
                      <div className="mt-3 p-2 rounded-xl bg-error-container/20 border border-error/30 text-xs text-error font-medium">
                        {med.allergy_warning}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Confirm & Persist to Memory */}
            <div className="mt-8 pt-6 border-t border-outline-variant/40 flex flex-col sm:flex-row items-center justify-between gap-4">
              <div>
                <p className="font-bold text-xs md:text-sm text-on-surface flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-primary text-base">psychology</span>
                  <span>Sync to Health Memory & Active Profile</span>
                </p>
                <p className="text-xs text-secondary mt-0.5">
                  Saves these medications so your AI Doctor remembers your regimen across all chats.
                </p>
              </div>

              <div className="flex items-center gap-2.5 w-full sm:w-auto">
                <button
                  disabled={confirmingPrescription}
                  onClick={handleConfirmPrescription}
                  className="flex-1 sm:flex-initial inline-flex items-center justify-center gap-2 px-6 py-3 rounded-2xl font-bold text-xs bg-primary text-on-primary hover:opacity-95 shadow-xs transition-all active:scale-98"
                >
                  <span className="material-symbols-outlined text-base">save</span>
                  <span>
                    {confirmingPrescription ? 'Saving to Memory...' : 'Confirm & Save Medications'}
                  </span>
                </button>

                <button
                  onClick={() => navigate('/chat')}
                  className="inline-flex items-center gap-1.5 px-4 py-3 rounded-2xl font-bold text-xs bg-primary-container text-on-primary-container hover:opacity-90 transition-all shadow-xs"
                >
                  <span className="material-symbols-outlined text-base">chat</span>
                  <span>Ask AI Doctor</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
