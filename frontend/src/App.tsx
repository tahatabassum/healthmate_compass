import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { AppLayout } from './components/layout/AppLayout';
import { LoginPage } from './pages/LoginPage';
import { HomeDashboardPage } from './pages/HomeDashboardPage';
import { ReportTranslatePage } from './pages/ReportTranslatePage';
import { AIConsultPage } from './pages/AIConsultPage';
import { DoctorFinderPage } from './pages/DoctorFinderPage';
import { HealthMemoryPage } from './pages/HealthMemoryPage';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public Authentication Route */}
          <Route path="/login" element={<LoginPage />} />

          {/* Protected Routes */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <AppLayout>
                  <HomeDashboardPage />
                </AppLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/translate"
            element={
              <ProtectedRoute>
                <AppLayout>
                  <ReportTranslatePage />
                </AppLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/reports"
            element={
              <ProtectedRoute>
                <AppLayout>
                  <ReportTranslatePage />
                </AppLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/reports/:reportId"
            element={
              <ProtectedRoute>
                <AppLayout>
                  <ReportTranslatePage />
                </AppLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/consult"
            element={
              <ProtectedRoute>
                <AppLayout>
                  <AIConsultPage />
                </AppLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/doctors"
            element={
              <ProtectedRoute>
                <AppLayout>
                  <DoctorFinderPage />
                </AppLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/memory"
            element={
              <ProtectedRoute>
                <AppLayout>
                  <HealthMemoryPage />
                </AppLayout>
              </ProtectedRoute>
            }
          />

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;
