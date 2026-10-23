import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import api from '../lib/api';

interface DoctorItem {
  place_id: string;
  name: string;
  address: string;
  lat?: number;
  lng?: number;
  rating?: number;
  rating_count?: number;
  phone?: string;
  open_now?: boolean;
  maps_url: string;
  distance_m?: number;
  specialty: string;
}

const SPECIALTIES = [
  'General Physician',
  'Cardiologist',
  'Endocrinologist',
  'Nephrologist',
  'Gastroenterologist',
  'Hematologist',
  'Dermatologist',
  'Neurologist',
  'Pulmonologist',
  'Orthopedic',
  'ENT',
  'Ophthalmologist',
  'Gynecologist',
  'Pediatrician',
  'Psychiatrist',
  'Urologist',
  'Rheumatologist',
  'Dentist',
];

export const DoctorFinderPage: React.FC = () => {
  const [searchParams] = useSearchParams();

  const initialSpecialty = searchParams.get('specialty') || 'General Physician';
  const [specialty, setSpecialty] = useState<string>(initialSpecialty);
  const [city, setCity] = useState<string>('Faisalabad');
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [doctors, setDoctors] = useState<DoctorItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [fallbackMessage, setFallbackMessage] = useState<string | null>(null);
  const [selectedDoctor, setSelectedDoctor] = useState<DoctorItem | null>(null);

  useEffect(() => {
    const specFromUrl = searchParams.get('specialty');
    if (specFromUrl && SPECIALTIES.includes(specFromUrl)) {
      setSpecialty(specFromUrl);
    }
  }, [searchParams]);

  const fetchDoctors = async (lat?: number, lng?: number, searchCity?: string) => {
    setLoading(true);
    setFallbackMessage(null);
    try {
      const params: any = {
        specialty,
        radius: 8000,
      };

      if (lat && lng) {
        params.lat = lat;
        params.lng = lng;
      } else if (searchCity) {
        params.city = searchCity;
      }

      const res = await api.get('/api/doctors', { params });
      const docs = res.data.doctors || [];
      setDoctors(docs);
      if (res.data.fallback_used && res.data.fallback_message) {
        setFallbackMessage(res.data.fallback_message);
      }
      if (docs.length > 0) {
        setSelectedDoctor(docs[0]);
      } else {
        setSelectedDoctor(null);
      }
    } catch (err) {
      console.error('Failed to load doctors:', err);
      setDoctors([]);
      setSelectedDoctor(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    setUserLocation(null);
    fetchDoctors(undefined, undefined, city);
  };

  useEffect(() => {
    if (userLocation) {
      fetchDoctors(userLocation.lat, userLocation.lng);
    } else {
      fetchDoctors(undefined, undefined, city);
    }
  }, [specialty]);

  const handleUseLocation = () => {
    if ('geolocation' in navigator) {
      setLoading(true);
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const loc = {
            lat: position.coords.latitude,
            lng: position.coords.longitude,
          };
          setUserLocation(loc);
          fetchDoctors(loc.lat, loc.lng);
        },
        (error) => {
          console.warn('Geolocation denied or unavailable:', error);
          fetchDoctors(undefined, undefined, city);
        }
      );
    }
  };

  const formatDistance = (meters?: number) => {
    if (meters === undefined || meters === null) return null;
    if (meters < 1000) return `${meters} m away`;
    return `${(meters / 1000).toFixed(1)} km away`;
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 md:py-8 space-y-6">
      {/* ── HEADER ────────────────────────────────────────────────────────── */}
      <div>
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-container text-primary text-xs font-bold mb-2 border border-outline-variant/50">
          <span
            className="material-symbols-outlined text-sm text-primary"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            verified_user
          </span>
          <span>Google Places API (New) • Zero Hallucinations</span>
        </div>
        <h1 className="text-2xl md:text-3xl font-extrabold text-on-surface tracking-tight">
          Find Nearby Specialists & Clinics
        </h1>
        <p className="text-xs md:text-sm text-secondary mt-1">
          Directly verified clinics and hospitals with ratings, operating hours, phone numbers, and Google Maps directions.
        </p>
      </div>

      {/* ── FILTER TOOLBAR ─────────────────────────────────────────────────── */}
      <div className="bg-surface-container-lowest rounded-3xl border border-outline-variant/60 p-4 shadow-xs grid grid-cols-1 sm:grid-cols-3 gap-3">
        {/* Specialty Selector */}
        <div>
          <label className="block text-[11px] font-bold text-secondary uppercase tracking-wider mb-1.5">
            Medical Specialty
          </label>
          <select
            value={specialty}
            onChange={(e) => setSpecialty(e.target.value)}
            className="w-full bg-surface-container-low border border-outline-variant/60 rounded-2xl px-3.5 py-2.5 text-xs md:text-sm font-semibold text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/20"
          >
            {SPECIALTIES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        {/* City Input */}
        <div>
          <label className="block text-[11px] font-bold text-secondary uppercase tracking-wider mb-1.5">
            City or Area
          </label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input
                type="text"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="e.g. Quetta, Faisalabad, Lahore"
                className="w-full bg-surface-container-low border border-outline-variant/60 rounded-2xl pl-10 pr-3.5 py-2.5 text-xs md:text-sm font-medium text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
              <span className="material-symbols-outlined text-secondary absolute left-3 top-3 text-lg">
                search
              </span>
            </div>
            <button
              onClick={handleSearch}
              className="py-2.5 px-4 rounded-2xl bg-primary text-white hover:bg-primary/90 text-xs font-bold shadow-xs flex items-center justify-center gap-1.5 transition-all active:scale-95"
            >
              <span>Search</span>
            </button>
          </div>
        </div>

        {/* Geolocation Button */}
        <div className="flex items-end">
          <button
            onClick={handleUseLocation}
            className="w-full py-2.5 px-4 rounded-2xl bg-primary-container text-on-primary-container hover:opacity-95 text-xs font-bold shadow-xs flex items-center justify-center gap-2 transition-all active:scale-98"
          >
            <span
              className="material-symbols-outlined text-base"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              near_me
            </span>
            <span>Use My Location</span>
          </button>
        </div>
      </div>

      {/* Fallback alert if general physician used */}
      {fallbackMessage && (
        <div className="p-3.5 bg-surface-container-low border border-outline-variant/60 rounded-2xl text-secondary text-xs flex items-center gap-2.5">
          <span className="material-symbols-outlined text-primary text-base">info</span>
          <span>{fallbackMessage}</span>
        </div>
      )}

      {/* ── MAIN CONTENT (List + Map Preview) ──────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Doctor Cards List */}
        <div className="lg:col-span-7 space-y-4">
          <div className="flex items-center justify-between text-xs text-secondary font-bold uppercase tracking-wider px-1">
            <span>
              {doctors.length} Verified {specialty} Providers Found
            </span>
            <span>Data from Google Maps</span>
          </div>

          {loading ? (
            <div className="bg-surface-container-lowest rounded-3xl border border-outline-variant/60 p-12 text-center text-secondary flex flex-col items-center justify-center gap-3">
              <span className="material-symbols-outlined text-3xl text-primary animate-spin">
                progress_activity
              </span>
              <span className="text-xs font-medium">Finding nearby specialists on Google Maps…</span>
            </div>
          ) : doctors.length === 0 ? (
            <div className="bg-surface-container-lowest rounded-3xl border border-outline-variant/60 p-10 text-center text-secondary">
              <span className="material-symbols-outlined text-4xl text-outline-variant mb-2">
                location_off
              </span>
              <p className="font-semibold text-on-surface">No clinics found for this specialty in this radius.</p>
              <p className="text-xs text-secondary mt-1">Try widening the city or selecting General Physician.</p>
            </div>
          ) : (
            doctors.map((doc) => {
              const isSelected = selectedDoctor?.place_id === doc.place_id;
              return (
                <div
                  key={doc.place_id}
                  onClick={() => setSelectedDoctor(doc)}
                  className={`bg-surface-container-lowest rounded-3xl border p-5 transition-all cursor-pointer shadow-xs ${
                    isSelected
                      ? 'border-primary ring-2 ring-primary/20'
                      : 'border-outline-variant/60 hover:border-outline'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-bold text-on-surface text-base leading-snug">
                        {doc.name}
                      </h3>
                      <p className="text-xs text-secondary mt-1 flex items-center gap-1.5">
                        <span className="material-symbols-outlined text-sm text-secondary">
                          location_on
                        </span>
                        <span>{doc.address}</span>
                      </p>
                    </div>

                    {doc.open_now !== undefined && (
                      <span
                        className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full shrink-0 flex items-center gap-1 ${
                          doc.open_now
                            ? 'bg-[#DCFCE7] text-[#16A34A]'
                            : 'bg-surface-container text-secondary'
                        }`}
                      >
                        <span className="material-symbols-outlined text-xs">schedule</span>
                        {doc.open_now ? 'Open Now' : 'Closed'}
                      </span>
                    )}
                  </div>

                  {/* Rating & Distance */}
                  <div className="flex items-center gap-4 mt-3 pt-3 border-t border-outline-variant/30 text-xs">
                    {doc.rating && (
                      <div className="flex items-center gap-1 text-[#D97706] font-bold">
                        <span
                          className="material-symbols-outlined text-sm"
                          style={{ fontVariationSettings: "'FILL' 1" }}
                        >
                          star
                        </span>
                        <span>{doc.rating}</span>
                        <span className="text-secondary font-normal">
                          ({doc.rating_count || 0})
                        </span>
                      </div>
                    )}

                    {doc.distance_m !== undefined && (
                      <div className="text-primary font-semibold bg-surface-container px-2 py-0.5 rounded-md text-[11px]">
                        {formatDistance(doc.distance_m)}
                      </div>
                    )}
                  </div>

                  {/* Open in Google Maps */}
                  <div className="mt-3">
                    <a
                      href={doc.maps_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="inline-flex items-center gap-1 text-xs font-bold text-primary hover:underline"
                    >
                      <span>Open Directions in Google Maps</span>
                      <span className="material-symbols-outlined text-sm">open_in_new</span>
                    </a>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Map Visualization Preview Panel */}
        <div className="lg:col-span-5">
          <div className="bg-surface-container-lowest rounded-3xl border border-outline-variant/60 shadow-xs p-6 sticky top-24">
            <h3 className="font-bold text-on-surface text-sm md:text-base mb-2 flex items-center gap-2">
              <span className="material-symbols-outlined text-primary text-lg">map</span>
              <span>Clinic Location Overview</span>
            </h3>

            {/* Real Interactive Google Maps Embed Canvas */}
            <div className="w-full h-72 bg-surface-container-low rounded-2xl relative overflow-hidden border border-outline-variant/60 shadow-inner mb-4">
              <iframe
                title="Clinic Map View"
                width="100%"
                height="100%"
                style={{ border: 0 }}
                loading="lazy"
                referrerPolicy="no-referrer-when-downgrade"
                src={
                  selectedDoctor?.lat && selectedDoctor?.lng
                    ? `https://maps.google.com/maps?q=${selectedDoctor.lat},${selectedDoctor.lng}&t=&z=15&ie=UTF8&iwloc=&output=embed`
                    : selectedDoctor
                    ? `https://maps.google.com/maps?q=${encodeURIComponent(selectedDoctor.name + ' ' + selectedDoctor.address)}&t=&z=15&ie=UTF8&iwloc=&output=embed`
                    : city
                    ? `https://maps.google.com/maps?q=${encodeURIComponent(city + ', Pakistan')}&t=&z=13&ie=UTF8&iwloc=&output=embed`
                    : userLocation
                    ? `https://maps.google.com/maps?q=${userLocation.lat},${userLocation.lng}&t=&z=13&ie=UTF8&iwloc=&output=embed`
                    : `https://maps.google.com/maps?q=Pakistan&t=&z=6&ie=UTF8&iwloc=&output=embed`
                }
              />
            </div>

            {selectedDoctor ? (
              <div className="space-y-2">
                <span className="text-[10px] font-bold text-primary uppercase tracking-wider block">
                  Selected Clinic
                </span>
                <p className="font-bold text-on-surface text-sm">{selectedDoctor.name}</p>
                <p className="text-xs text-secondary leading-relaxed">{selectedDoctor.address}</p>
                <a
                  href={selectedDoctor.maps_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-full inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-2xl bg-primary text-white hover:bg-primary/90 font-bold text-xs shadow-xs mt-3 transition-all active:scale-98"
                >
                  <span>Open Directions in Google Maps</span>
                  <span className="material-symbols-outlined text-sm">open_in_new</span>
                </a>
              </div>
            ) : (
              <div className="text-center py-4 text-xs text-secondary">
                Select a clinic from the list to view its exact location and directions.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
