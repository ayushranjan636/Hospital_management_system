const { createApp } = Vue;

console.log('✅ app.js loaded, Vue available:', typeof Vue !== 'undefined');

try {
    const app = createApp({
    data() {
        let savedUser = JSON.parse(localStorage.getItem('hms_user')) || null;
        // Fix for old corrupted cache format
        if (savedUser && savedUser.user && !savedUser.role) {
            savedUser = { ...savedUser.user, token: savedUser.token };
            localStorage.setItem('hms_user', JSON.stringify(savedUser));
        }

        return {
            state: {
                user: savedUser,
            },
            currentView: savedUser ? 'dashboard' : 'landing',
            
            // Auth Forms
            loginForm: { username: '', password: '' },
            registerForm: { username: '', email: '', password: '', role: 'patient' },
            
            // Admin
            adminTab: 'doctors',
            doctors: [],
            patients: [],
            allAppointments: [],
            adminData: {},
            newDoctorForm: { name: '', username: '', email: '', specialization: '', password: '', department_name: 'General' },
            showEditDoctorModal: false,
            editDoctorForm: { id: null, specialization: '', bio: '' },
            adminSearchQuery: '',
            adminSearchResults: { doctors: [], patients: [] },
            
            // Doctor
            doctorTab: 'appointments',
            doctorProfile: { charge_per_slot: 150.0, wallet_balance: 0.0 },
            doctorAppointments: [],
            myPatients: [],
            showPatientHistoryModal: false,
            currentPatientHistory: [],
            availability: Array(7).fill(null).map((_, i) => {
                const d = new Date();
                d.setDate(d.getDate() + i);
                return {
                    date: d.toISOString().split('T')[0],
                    display_day: d.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' }),
                    start_time: '10:00',
                    end_time: '18:00',
                    is_available: true
                };
            }),
            showTreatmentModal: false,
            treatmentForm: { diagnosis: '', prescription: '', notes: '' },
            currentAppointmentForTreatment: null,
            
            // Patient
            patientTab: 'book',
            upcomingAppointments: [],
            appointmentHistory: [],
            patientAppointments: [],  // Combined for template
            allDoctors: [],
            bookingFilters: { search: '' },
            selectedDoctor: null,
            showBookingModal: false,
            bookingForm: { date: '', time: '', patient_report: '' },
            patientProfile: { email: '', phone: '', dob: '', gender: '', address: '' },
            showRescheduleModal: false,
            rescheduleForm: { date: '', time: '' },
            currentAppointmentForReschedule: null,
            showPaymentModal: false,
            currentPaymentAppt: null,
            
            // Messages
            message: null,
        };
    },
    
    computed: {
        todayDate() {
            return new Date().toISOString().split('T')[0];
        },
        availableTimeSlots() {
            const slots = [];
            // "10AM to 6pm only with also add break slot"
            for (let h = 10; h < 18; h++) {
                if (h === 13) continue; // 1 PM to 2 PM break slot
                slots.push(`${h.toString().padStart(2, '0')}:00`);
                slots.push(`${h.toString().padStart(2, '0')}:30`);
            }
            return slots;
        },
        filteredDoctors() {
            const search = this.bookingFilters.search.toLowerCase();
            return this.allDoctors.filter(d => 
                d.name.toLowerCase().includes(search) || 
                d.specialization.toLowerCase().includes(search)
            );
        }
    },
    
    watch: {
        'state.user'(newVal) {
            if (newVal) {
                localStorage.setItem('hms_user', JSON.stringify(newVal));
                localStorage.setItem('hms_token', newVal.token);
                this.loadRoleData();
            } else {
                localStorage.removeItem('hms_user');
                localStorage.removeItem('hms_token');
            }
        }
    },
    
    mounted() {
        if (this.state.user) {
            this.loadRoleData();
        }
    },
    
    methods: {
        getAuthHeaders() {
            const token = localStorage.getItem('hms_token');
            return { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };
        },
        
        notify(message, type = 'success') {
            this.message = { text: message, type };
            setTimeout(() => { this.message = null; }, 5000);
        },
        
        async login() {
            try {
                const res = await axios.post('http://127.0.0.1:5000/api/auth/login', this.loginForm);
                const userObj = res.data.user;
                userObj.token = res.data.token;
                this.state.user = userObj;
                this.currentView = 'dashboard';
                this.notify('Logged in successfully');
            } catch (e) {
                this.notify('Login failed', 'error');
            }
        },
        
        async register() {
            try {
                const res = await axios.post('http://127.0.0.1:5000/api/auth/register', this.registerForm);
                this.notify('Account created! Please sign in');
                this.currentView = 'login';
            } catch (e) {
                this.notify('Registration failed', 'error');
            }
        },
        
        logout() {
            this.state.user = null;
            this.currentView = 'landing';
            this.notify('Logged out');
        },
        
        async loadRoleData() {
            if (this.state.user.role === 'admin') await this.loadAdmin();
            if (this.state.user.role === 'doctor') await this.loadDoctor();
            if (this.state.user.role === 'patient') await this.loadPatient();
        },
        
        // ADMIN METHODS
        async loadAdmin() {
            try {
                const res = await axios.get('http://127.0.0.1:5000/api/admin/dashboard', { headers: this.getAuthHeaders() });
                this.adminData = res.data;
                await this.loadAdminDoctors();
                await this.loadAdminPatients();
                await this.loadAllAppointments();
                this.renderAdminChart();
            } catch (e) {
                console.log('Admin load error:', e);
            }
        },
        
        renderAdminChart() {
            setTimeout(() => {
                const ctx = document.getElementById('adminChart');
                if (ctx) {
                    if (window.adminChartInstance) {
                        window.adminChartInstance.destroy();
                    }
                    window.adminChartInstance = new Chart(ctx, {
                        type: 'bar',
                        data: {
                            labels: ['Doctors', 'Patients', 'Appointments', 'Upcoming Today'],
                            datasets: [{
                                label: 'Platform Statistics',
                                data: [
                                    this.adminData.total_doctors,
                                    this.adminData.total_patients,
                                    this.adminData.total_appointments,
                                    this.adminData.upcoming_appointments
                                ],
                                backgroundColor: [
                                    'rgba(37, 99, 235, 0.5)',
                                    'rgba(16, 185, 129, 0.5)',
                                    'rgba(245, 158, 11, 0.5)',
                                    'rgba(239, 68, 68, 0.5)'
                                ],
                                borderColor: [
                                    'rgb(37, 99, 235)',
                                    'rgb(16, 185, 129)',
                                    'rgb(245, 158, 11)',
                                    'rgb(239, 68, 68)'
                                ],
                                borderWidth: 1
                            }]
                        },
                        options: {
                            responsive: true,
                            scales: {
                                y: {
                                    beginAtZero: true
                                }
                            }
                        }
                    });
                }
            }, 500);
        },
        
        async loadAdminDoctors() {
            try {
                const res = await axios.get('http://127.0.0.1:5000/api/admin/doctors', { headers: this.getAuthHeaders() });
                this.doctors = res.data;
            } catch (e) {
                console.log('Error loading doctors');
            }
        },
        
        async loadAdminPatients() {
            try {
                const res = await axios.get('http://127.0.0.1:5000/api/admin/patients', { headers: this.getAuthHeaders() });
                this.patients = res.data;
            } catch (e) {
                console.log('Error loading patients');
            }
        },
        
        async loadAllAppointments() {
            try {
                const res = await axios.get('http://127.0.0.1:5000/api/admin/appointments', { headers: this.getAuthHeaders() });
                this.allAppointments = res.data;
            } catch (e) {
                console.log('Error loading appointments');
            }
        },
        
        async addDoctor() {
            try {
                // Remove map name to username so user's specified username is preserved
                if (!this.newDoctorForm.username) {
                    this.newDoctorForm.username = this.newDoctorForm.name;
                }
                await axios.post('http://127.0.0.1:5000/api/admin/doctors', this.newDoctorForm, { headers: this.getAuthHeaders() });
                this.newDoctorForm = { name: '', email: '', specialization: '', password: '', department_name: 'General', username: '' };
                this.loadAdminDoctors();
                this.notify('Doctor added successfully');
            } catch (e) {
                this.notify('Error adding doctor. Check fields or if email exists.', 'error');
            }
        },
        
        openEditDoctor(doctor) {
            this.editDoctorForm = { 
                id: doctor.id, 
                username: doctor.username || doctor.name || '',
                specialization: doctor.specialization, 
                bio: doctor.bio || '',
                password: '' 
            };
            this.showEditDoctorModal = true;
        },

        async saveDoctorEdit() {
            try {
                await axios.put(`http://127.0.0.1:5000/api/admin/doctors/${this.editDoctorForm.id}`, this.editDoctorForm, { headers: this.getAuthHeaders() });
                this.showEditDoctorModal = false;
                this.loadAdminDoctors();
                this.notify('Doctor updated successfully');
            } catch (e) {
                this.notify('Error updating doctor', 'error');
            }
        },
        
        async performAdminSearch() {
            if (!this.adminSearchQuery) return;
            try {
                const res = await axios.get(`http://127.0.0.1:5000/api/admin/search?q=${this.adminSearchQuery}`, { headers: this.getAuthHeaders() });
                this.adminSearchResults = res.data;
            } catch (e) {
                this.notify('Search failed', 'error');
            }
        },

        async deleteDoctor(doctorId) {
            if(!confirm("Are you sure you want to completely delete this doctor?")) return;
            try {
                await axios.delete(`http://127.0.0.1:5000/api/admin/doctors/${doctorId}`, { headers: this.getAuthHeaders() });
                this.loadAdminDoctors();
                this.showEditDoctorModal = false;
                this.notify('Doctor completely deleted');
            } catch (e) {
                this.notify('Error deleting doctor', 'error');
            }
        },
        
        async triggerDailyReminders() {
            try {
                this.notify('Sending reminders (sync, please wait)...', 'info');
                const res = await axios.post(
                    'http://127.0.0.1:5000/api/admin/trigger-reminders',
                    { test_mode: true },
                    { headers: this.getAuthHeaders() }
                );
                const data = res.data || {};
                const extra = data.test_mail_sent ? ' (test confirmation mail sent)' : '';
                this.notify(`Daily reminders done. Sent: ${data.sent || 0}, Failed: ${data.failed || 0}, Total: ${data.total || 0}${extra}`);
            } catch (e) {
                this.notify('Error triggering reminders', 'error');
            }
        },
        
        async triggerMonthlyReports(reportFormat = 'html') {
            try {
                this.notify(`Sending ${reportFormat.toUpperCase()} reports (sync, please wait)...`, 'info');
                const res = await axios.post(
                    'http://127.0.0.1:5000/api/admin/trigger-monthly-reports',
                    { format: reportFormat },
                    { headers: this.getAuthHeaders() }
                );
                const data = res.data || {};
                const finalFormat = (data.format || reportFormat || 'html').toUpperCase();
                this.notify(`${finalFormat} monthly reports done. Sent: ${data.sent || 0}, Failed: ${data.failed || 0}, Total: ${data.total || 0}`);
            } catch (e) {
                this.notify('Error triggering monthly reports', 'error');
            }
        },

        async toggleDoctorStatus(doctor) {
            try {
                // If it's active right now, we set it to false, else to true
                let newStatus = !(doctor.is_active || (doctor.user && doctor.user.is_active));
                await axios.put(`http://127.0.0.1:5000/api/admin/doctors/${doctor.id}`, { is_active: newStatus }, { headers: this.getAuthHeaders() });
                this.loadAdminDoctors();
                this.notify('Doctor status toggled');
            } catch (e) {
                this.notify('Error toggling doctor', 'error');
            }
        },
        
        async deletePatient(patientId) {
            if(!confirm("Are you sure you want to completely delete this patient?")) return;
            try {
                await axios.delete(`http://127.0.0.1:5000/api/admin/patients/${patientId}`, { headers: this.getAuthHeaders() });
                this.loadAdminPatients();
                this.notify('Patient deleted');
            } catch (e) {
                this.notify('Error deleting patient', 'error');
            }
        },
        
        async disablePatient(patientId) {
            try {
                await axios.put(`http://127.0.0.1:5000/api/admin/patients/${patientId}`, { is_active: false }, { headers: this.getAuthHeaders() });
                this.loadAdminPatients();
                this.notify('Patient status updated');
            } catch (e) {
                this.notify('Error updating patient', 'error');
            }
        },
        
        async deleteAppointment(appointmentId) {
            try {
                await axios.delete(`http://127.0.0.1:5000/api/admin/appointments/${appointmentId}`, { headers: this.getAuthHeaders() });
                this.loadAllAppointments();
                this.notify('Appointment deleted');
            } catch (e) {
                this.notify('Error deleting appointment', 'error');
            }
        },
        
        // DOCTOR METHODS
        async loadDoctor() {
            try {
                const res = await axios.get('http://127.0.0.1:5000/api/doctor/dashboard', { headers: this.getAuthHeaders() });
                this.doctorAppointments = res.data.appointments || [];
                this.myPatients = res.data.patients || [];
                this.doctorProfile.charge_per_slot = res.data.charge_per_slot || 150.0;
                this.doctorProfile.wallet_balance = res.data.wallet_balance || 0.0;
            } catch (e) {
                console.log('Error loading doctor data');
            }
        },

        async updateDoctorProfile() {
            try {
                await axios.put('http://127.0.0.1:5000/api/doctor/profile', { charge_per_slot: this.doctorProfile.charge_per_slot }, { headers: this.getAuthHeaders() });
                this.notify('Charge per 30 minutes updated');
            } catch (e) {
                this.notify('Error updating charge', 'error');
            }
        },
        
        async updateAvailability() {
            try {
                const payload = { 
                    slots: this.availability.map((av) => ({
                        date: av.date,
                        start_time: av.start_time,
                        end_time: av.end_time,
                        is_available: av.is_available
                    }))
                };
                await axios.put('http://127.0.0.1:5000/api/doctor/availability', payload, { headers: this.getAuthHeaders() });
                this.notify('Availability updated');
            } catch (e) {
                this.notify('Error updating availability', 'error');
            }
        },
        
        openTreatmentForm(appointment) {
            this.currentAppointmentForTreatment = appointment;
            this.treatmentForm = { diagnosis: '', prescription: '', notes: '' };
            this.showTreatmentModal = true;
        },
        
        async saveTreatment() {
            try {
                await axios.post(`http://127.0.0.1:5000/api/doctor/appointments/${this.currentAppointmentForTreatment.id}/complete`, 
                    this.treatmentForm, { headers: this.getAuthHeaders() });
                this.showTreatmentModal = false;
                this.loadDoctor();
                if (this.showPatientHistoryModal) {
                    this.viewPatientHistory(this.currentAppointmentForTreatment.patient_id);
                }
                this.notify('Treatment saved successfully!');
            } catch (e) {
                this.notify('Error saving treatment', 'error');
            }
        },
        
        async viewPatientHistory(patientId) {
            try {
                const res = await axios.get(`http://127.0.0.1:5000/api/doctor/patients/${patientId}/history`, { headers: this.getAuthHeaders() });
                this.currentPatientHistory = res.data || [];
                this.showPatientHistoryModal = true;
            } catch (e) {
                this.notify('Error loading patient history', 'error');
            }
        },
        
        editTreatment(appt) {
            this.currentAppointmentForTreatment = appt;
            this.treatmentForm = {
                diagnosis: appt.treatment?.diagnosis || '',
                prescription: appt.treatment?.prescription || '',
                notes: appt.treatment?.notes || ''
            };
            this.showTreatmentModal = true;
        },
        
        // PATIENT METHODS
        async loadPatient() {
            try {
                const res = await axios.get('http://127.0.0.1:5000/api/patient/dashboard', { headers: this.getAuthHeaders() });
                this.upcomingAppointments = res.data.upcoming || [];
                this.appointmentHistory = res.data.history || [];
                this.patientAppointments = [...this.upcomingAppointments, ...this.appointmentHistory];
                await this.loadDoctors();
                await this.loadPatientProfile();
            } catch (e) {
                console.log('Error loading patient data');
            }
        },
        
        async loadDoctors() {
            try {
                const res = await axios.get('http://127.0.0.1:5000/api/patient/doctors', { headers: this.getAuthHeaders() });
                this.allDoctors = res.data;
            } catch (e) {
                console.log('Error loading doctors');
            }
        },
        
        selectDoctorForBooking(doctor) {
            this.selectedDoctor = doctor;
            this.showBookingModal = true;
            this.bookingForm = { date: '', time: '', patient_report: '' };
        },
        
        async saveBooking() {
            try {
                const res = await axios.post('http://127.0.0.1:5000/api/patient/appointments', {
                    doctor_id: this.selectedDoctor.id,
                    date: this.bookingForm.date,
                    time: this.bookingForm.time,
                    patient_report: this.bookingForm.patient_report || ''
                }, { headers: this.getAuthHeaders() });
                this.showBookingModal = false;
                this.loadPatient();
                const txn = res.data.transaction_id || `TXN-DEMO-${Math.floor(Math.random()*1000)}`;
                this.notify(`Payment processed! Txn: ${txn}. Appointment booked successfully.`);
            } catch (e) {
                this.notify('Error booking appointment', 'error');
            }
        },
        
        openRescheduleForm(appointment) {
            this.currentAppointmentForReschedule = appointment;
            this.rescheduleForm = { date: '', time: '' };
            this.showRescheduleModal = true;
        },
        
        async completeReschedule() {
            try {
                await axios.put(`http://127.0.0.1:5000/api/patient/appointments/${this.currentAppointmentForReschedule.id}/reschedule`,
                    { date: this.rescheduleForm.date, time: this.rescheduleForm.time },
                    { headers: this.getAuthHeaders() });
                this.showRescheduleModal = false;
                this.loadPatient();
                this.notify('Appointment rescheduled');
            } catch (e) {
                this.notify('Error rescheduling appointment', 'error');
            }
        },
        
        async cancelAppointment(appointmentId) {
            try {
                await axios.delete(`http://127.0.0.1:5000/api/patient/appointments/${appointmentId}`, { headers: this.getAuthHeaders() });
                this.loadPatient();
                this.notify('Appointment cancelled');
            } catch (e) {
                this.notify('Error cancelling appointment', 'error');
            }
        },
        
        async loadPatientProfile() {
            try {
                const res = await axios.get('http://127.0.0.1:5000/api/patient/profile', { headers: this.getAuthHeaders() });
                this.patientProfile = res.data;
            } catch (e) {
                console.log('Error loading profile');
            }
        },
        
        async updatePatientProfile() {
            try {
                await axios.put('http://127.0.0.1:5000/api/patient/profile', this.patientProfile, { headers: this.getAuthHeaders() });
                this.notify('Profile updated successfully');
            } catch (e) {
                this.notify('Error updating profile', 'error');
            }
        },
        
        async exportTreatmentCSV() {
            try {
                this.notify('Starting export...', 'info');
                const res = await axios.post('http://127.0.0.1:5000/api/patient/export', {}, { headers: this.getAuthHeaders() });
                const taskId = res.data.task_id;
                
                // Poll for completion
                const checkDownload = setInterval(async () => {
                    try {
                        const downloadRes = await axios.get(`http://127.0.0.1:5000/api/patient/export/${taskId}`, { 
                            headers: this.getAuthHeaders(),
                            responseType: 'blob'
                        });
                        
                        if (downloadRes.status === 200) {
                            clearInterval(checkDownload);
                            // Trigger download using blob
                            const blob = new Blob([downloadRes.data], { type: 'text/csv' });
                            const link = document.createElement('a');
                            link.href = window.URL.createObjectURL(blob);
                            link.download = `treatment_history.csv`;
                            document.body.appendChild(link);
                            link.click();
                            document.body.removeChild(link);
                            this.notify('Treatment history downloaded successfully');
                        }
                    } catch (e) {
                        if (e.response && e.response.status === 202) {
                            // Still processing
                            return;
                        }
                        clearInterval(checkDownload);
                        this.notify('Error downloading CSV', 'error');
                    }
                }, 1000);
                
                // Stop polling after 60 seconds
                setTimeout(() => clearInterval(checkDownload), 60000);
            } catch (e) {
                this.notify('Error exporting CSV', 'error');
            }
        },

        openPaymentPortal(appointment) {
            this.currentPaymentAppt = appointment;
            this.showPaymentModal = true;
        },

        processPayment() {
            setTimeout(() => {
                this.showPaymentModal = false;
                this.notify(`Payment of $150 for Dr. ${this.currentPaymentAppt.doctor_name} processed successfully!`);
                this.currentPaymentAppt = null;
            }, 1000);
        }
    }
    });
    
    app.mount('#app');
    console.log('✅ Vue app mounted successfully');
} catch (error) {
    console.error('❌ Error in app.js:', error);
    document.getElementById('app').innerHTML = '<div style="color: red; padding: 20px;"><h2>⚠️ Application Error</h2><p>' + error.message + '</p><p style="font-family: monospace; font-size: 12px; color: gray;">' + error.stack + '</p></div>';
}
