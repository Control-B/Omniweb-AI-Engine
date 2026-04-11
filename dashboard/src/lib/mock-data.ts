// Mock data for the dashboard preview — no API calls needed.
// Replace with real fetch() calls to omniweb-agent-engine when connecting.

export interface CallRecord {
  id: string;
  caller_number: string;
  direction: "inbound" | "outbound";
  status: "completed" | "in_progress" | "failed" | "no_answer" | "missed";
  duration_seconds: number | null;
  started_at: string;
  post_call_processed: boolean;
  transcript?: TranscriptTurn[];
  lead_id?: string;
}

export interface TranscriptTurn {
  speaker: "agent" | "caller";
  text: string;
  timestamp: number;
}

export interface LeadRecord {
  id: string;
  call_id: string;
  caller_name: string;
  caller_phone: string;
  caller_email: string | null;
  intent: string;
  urgency: "low" | "medium" | "high" | "emergency";
  summary: string;
  services_requested: string[];
  status: "new" | "contacted" | "booked" | "closed" | "lost";
  lead_score: number;
  follow_up_sent: boolean;
  created_at: string;
}

export interface PhoneNumberRecord {
  id: string;
  phone_number: string;
  friendly_name: string;
  is_active: boolean;
  livekit_sip_trunk_id: string | null;
  monthly_rate: number;
  total_calls: number;
}

export interface AgentConfigData {
  agent_name: string;
  agent_greeting: string;
  system_prompt: string;
  voice_id: string;
  voice_stability: number;
  voice_similarity_boost: number;
  llm_model: string;
  temperature: number;
  business_name: string;
  business_type: string;
  timezone: string;
  booking_url: string;
  business_hours: Record<string, { open: string; close: string } | null>;
  services: string[];
  after_hours_message: string;
  after_hours_sms_enabled: boolean;
  allow_interruptions: boolean;
  min_endpointing_delay: number;
  max_endpointing_delay: number;
}

export interface AnalyticsSummary {
  total_calls: number;
  completed_calls: number;
  avg_duration_seconds: number;
  total_leads: number;
  leads_by_status: Record<string, number>;
  conversion_rate: number;
  calls_today: number;
  calls_this_week: number;
  missed_calls: number;
}

// ── Mock data ────────────────────────────────────────────────────────────────

export const MOCK_ANALYTICS: AnalyticsSummary = {
  total_calls: 1247,
  completed_calls: 1089,
  avg_duration_seconds: 194,
  total_leads: 312,
  leads_by_status: { new: 47, contacted: 89, booked: 134, closed: 28, lost: 14 },
  conversion_rate: 28.6,
  calls_today: 23,
  calls_this_week: 156,
  missed_calls: 34,
};

export const MOCK_CALLS: CallRecord[] = [
  {
    id: "c001", caller_number: "+12125551234", direction: "inbound",
    status: "completed", duration_seconds: 247, started_at: "2026-04-11T14:32:00Z",
    post_call_processed: true, lead_id: "l001",
    transcript: [
      { speaker: "agent", text: "Thank you for calling Bob's Plumbing! This is Aria. How can I help you today?", timestamp: 0 },
      { speaker: "caller", text: "Hi, yeah, I've got a leak under my kitchen sink. It's been dripping all morning.", timestamp: 4.2 },
      { speaker: "agent", text: "I'm sorry to hear that! A kitchen sink leak can definitely be stressful. Let me get some details so we can help you as quickly as possible. Can I get your name?", timestamp: 8.1 },
      { speaker: "caller", text: "Sure, it's Michael Torres.", timestamp: 15.3 },
      { speaker: "agent", text: "Thank you, Michael. And is this the best number to reach you at?", timestamp: 18.0 },
      { speaker: "caller", text: "Yes, this is my cell.", timestamp: 21.5 },
      { speaker: "agent", text: "Perfect. Now, would you say this is an emergency — like active flooding — or is it more of a steady drip?", timestamp: 23.0 },
      { speaker: "caller", text: "It's a steady drip. Not flooding, but I've got a bucket under there and it fills up every couple hours.", timestamp: 28.1 },
      { speaker: "agent", text: "Got it — so it's urgent but not an emergency. We have a technician available tomorrow morning between 8 and 10 AM. Would that work for you?", timestamp: 35.2 },
      { speaker: "caller", text: "Tomorrow morning works great.", timestamp: 42.0 },
      { speaker: "agent", text: "Wonderful! I've got you scheduled for tomorrow morning. You'll get a confirmation text shortly. Is there anything else I can help with?", timestamp: 44.5 },
      { speaker: "caller", text: "No, that's it. Thanks so much!", timestamp: 51.0 },
      { speaker: "agent", text: "You're welcome, Michael! We'll see you tomorrow. Have a great rest of your day!", timestamp: 53.5 },
    ],
  },
  {
    id: "c002", caller_number: "+13475559876", direction: "inbound",
    status: "completed", duration_seconds: 183, started_at: "2026-04-11T13:15:00Z",
    post_call_processed: true, lead_id: "l002",
  },
  {
    id: "c003", caller_number: "+16465553333", direction: "inbound",
    status: "completed", duration_seconds: 312, started_at: "2026-04-11T11:45:00Z",
    post_call_processed: true, lead_id: "l003",
  },
  {
    id: "c004", caller_number: "+19175554444", direction: "outbound",
    status: "completed", duration_seconds: 95, started_at: "2026-04-11T10:30:00Z",
    post_call_processed: true,
  },
  {
    id: "c005", caller_number: "+12125555555", direction: "inbound",
    status: "no_answer", duration_seconds: null, started_at: "2026-04-11T09:55:00Z",
    post_call_processed: false,
  },
  {
    id: "c006", caller_number: "+17185556666", direction: "inbound",
    status: "completed", duration_seconds: 421, started_at: "2026-04-10T16:20:00Z",
    post_call_processed: true, lead_id: "l004",
  },
  {
    id: "c007", caller_number: "+12015557777", direction: "inbound",
    status: "completed", duration_seconds: 156, started_at: "2026-04-10T14:05:00Z",
    post_call_processed: true,
  },
  {
    id: "c008", caller_number: "+19295558888", direction: "outbound",
    status: "failed", duration_seconds: null, started_at: "2026-04-10T11:30:00Z",
    post_call_processed: false,
  },
  {
    id: "c009", caller_number: "+13475559999", direction: "inbound",
    status: "completed", duration_seconds: 267, started_at: "2026-04-10T09:15:00Z",
    post_call_processed: true, lead_id: "l005",
  },
  {
    id: "c010", caller_number: "+12125550000", direction: "inbound",
    status: "completed", duration_seconds: 189, started_at: "2026-04-09T15:40:00Z",
    post_call_processed: true,
  },
];

export const MOCK_LEADS: LeadRecord[] = [
  {
    id: "l001", call_id: "c001", caller_name: "Michael Torres", caller_phone: "+12125551234",
    caller_email: null, intent: "repair", urgency: "high",
    summary: "Kitchen sink leak — steady drip, bucket filling every 2 hours. Scheduled for tomorrow 8-10 AM.",
    services_requested: ["pipe repair", "leak detection"], status: "booked",
    lead_score: 0.92, follow_up_sent: true, created_at: "2026-04-11T14:36:00Z",
  },
  {
    id: "l002", call_id: "c002", caller_name: "Sarah Kim", caller_phone: "+13475559876",
    caller_email: "sarahk@email.com", intent: "quote", urgency: "medium",
    summary: "Bathroom remodel — wants quote for full master bath renovation. Budget around $15K.",
    services_requested: ["bathroom remodel", "fixture installation"], status: "contacted",
    lead_score: 0.85, follow_up_sent: true, created_at: "2026-04-11T13:18:00Z",
  },
  {
    id: "l003", call_id: "c003", caller_name: "James Wright", caller_phone: "+16465553333",
    caller_email: null, intent: "emergency", urgency: "emergency",
    summary: "Water heater burst in basement — active flooding. Dispatched emergency crew immediately.",
    services_requested: ["water heater", "emergency plumbing"], status: "booked",
    lead_score: 0.98, follow_up_sent: true, created_at: "2026-04-11T11:50:00Z",
  },
  {
    id: "l004", call_id: "c006", caller_name: "Linda Patel", caller_phone: "+17185556666",
    caller_email: "linda.patel@gmail.com", intent: "maintenance", urgency: "low",
    summary: "Annual drain cleaning for 3 bathroom drains + kitchen. Repeat customer, 2nd year.",
    services_requested: ["drain cleaning"], status: "booked",
    lead_score: 0.78, follow_up_sent: false, created_at: "2026-04-10T16:27:00Z",
  },
  {
    id: "l005", call_id: "c009", caller_name: "David Chen", caller_phone: "+13475559999",
    caller_email: "dchen@outlook.com", intent: "quote", urgency: "medium",
    summary: "Sewer line inspection — smells sewer gas in basement. Wants camera inspection quote.",
    services_requested: ["sewer line", "leak detection"], status: "new",
    lead_score: 0.71, follow_up_sent: false, created_at: "2026-04-10T09:20:00Z",
  },
];

export const MOCK_NUMBERS: PhoneNumberRecord[] = [
  {
    id: "n001", phone_number: "+12125559001", friendly_name: "Bob's Plumbing Main Line",
    is_active: true, livekit_sip_trunk_id: "ST_abc123", monthly_rate: 1.0, total_calls: 892,
  },
  {
    id: "n002", phone_number: "+17185559002", friendly_name: "Brooklyn Service Line",
    is_active: true, livekit_sip_trunk_id: "ST_def456", monthly_rate: 1.0, total_calls: 355,
  },
];

export const MOCK_AGENT_CONFIG: AgentConfigData = {
  agent_name: "Aria",
  agent_greeting: "Thank you for calling Bob's Plumbing! This is Aria. How can I help you today?",
  system_prompt: `You are Aria, the friendly AI receptionist for Bob's Plumbing.

Your goals:
1. Greet every caller warmly and understand their plumbing issue
2. Collect their name and phone number early in the conversation
3. Assess urgency: is this an emergency (active leak, flooding) or routine?
4. For emergencies: prioritize and get the call to the team ASAP
5. For routine jobs: collect details and schedule an appointment
6. Always be empathetic — plumbing problems are stressful!

Services offered: emergency plumbing, drain cleaning, water heater installation/repair, pipe repair/replacement, bathroom remodels, sewer line work, faucet/fixture installation.

Business hours: Monday-Friday 7am-6pm, Saturday 8am-3pm. Emergency service 24/7.

Keep responses brief and conversational. You are on a phone call.`,
  voice_id: "21m00Tcm4TlvDq8ikWAM",
  voice_stability: 0.5,
  voice_similarity_boost: 0.75,
  llm_model: "gpt-4o",
  temperature: 0.7,
  business_name: "Bob's Plumbing",
  business_type: "plumbing",
  timezone: "America/New_York",
  booking_url: "https://bobs-plumbing.demo/book",
  business_hours: {
    monday: { open: "07:00", close: "18:00" },
    tuesday: { open: "07:00", close: "18:00" },
    wednesday: { open: "07:00", close: "18:00" },
    thursday: { open: "07:00", close: "18:00" },
    friday: { open: "07:00", close: "18:00" },
    saturday: { open: "08:00", close: "15:00" },
    sunday: null,
  },
  services: ["Emergency Plumbing", "Drain Cleaning", "Water Heater", "Pipe Repair", "Bathroom Remodel", "Sewer Line", "Fixture Installation"],
  after_hours_message: "We're currently closed but will call you back first thing. For emergencies, stay on the line.",
  after_hours_sms_enabled: true,
  allow_interruptions: true,
  min_endpointing_delay: 0.3,
  max_endpointing_delay: 0.8,
};

// Weekly call volume for chart
export const MOCK_WEEKLY_CALLS = [
  { day: "Mon", calls: 28, leads: 8 },
  { day: "Tue", calls: 32, leads: 11 },
  { day: "Wed", calls: 25, leads: 7 },
  { day: "Thu", calls: 35, leads: 12 },
  { day: "Fri", calls: 30, leads: 9 },
  { day: "Sat", calls: 18, leads: 5 },
  { day: "Sun", calls: 4, leads: 1 },
];

// Hourly distribution for chart
export const MOCK_HOURLY_CALLS = [
  { hour: "7am", calls: 3 },
  { hour: "8am", calls: 8 },
  { hour: "9am", calls: 14 },
  { hour: "10am", calls: 18 },
  { hour: "11am", calls: 15 },
  { hour: "12pm", calls: 11 },
  { hour: "1pm", calls: 13 },
  { hour: "2pm", calls: 16 },
  { hour: "3pm", calls: 12 },
  { hour: "4pm", calls: 9 },
  { hour: "5pm", calls: 6 },
  { hour: "6pm", calls: 2 },
];
