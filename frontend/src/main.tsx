import { StrictMode, type ReactNode, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  BadgeCheck,
  Bell,
  BookOpenCheck,
  BriefcaseMedical,
  CalendarClock,
  CheckCircle2,
  ClipboardList,
  Database,
  FileHeart,
  HeartPulse,
  LayoutDashboard,
  Loader2,
  MessageSquareText,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  UserCheck
} from "lucide-react";
import "./styles.css";

type View = "overview" | "consultation" | "jobs" | "verification" | "knowledge" | "settings";

type Metric = {
  label: string;
  value: string;
  detail: string;
  tone: "green" | "amber" | "blue" | "rose";
};

type ChatResponse = {
  answer: string;
  intent: {
    category: string;
    subcategory: string;
    confidence: number;
  };
  cache_hit_level: string;
  citations: Array<{ title: string; snippet: string; source_url?: string }>;
};

const navItems: Array<{ id: View; label: string; icon: ReactNode }> = [
  { id: "overview", label: "Overview", icon: <LayoutDashboard size={18} /> },
  { id: "consultation", label: "AI Consultation", icon: <MessageSquareText size={18} /> },
  { id: "jobs", label: "Care Jobs", icon: <BriefcaseMedical size={18} /> },
  { id: "verification", label: "Verification", icon: <UserCheck size={18} /> },
  { id: "knowledge", label: "Knowledge Base", icon: <BookOpenCheck size={18} /> },
  { id: "settings", label: "System", icon: <Settings size={18} /> }
];

const metrics: Metric[] = [
  { label: "AI sessions", value: "1,284", detail: "+18.6% this week", tone: "green" },
  { label: "Care jobs", value: "326", detail: "72 awaiting match", tone: "blue" },
  { label: "Verification queue", value: "41", detail: "12 high priority", tone: "amber" },
  { label: "Risk alerts", value: "8", detail: "all routed to urgent flow", tone: "rose" }
];

const pipelines = [
  { label: "Emergency filter", value: 100, status: "active" },
  { label: "Intent classifier", value: 96, status: "healthy" },
  { label: "RAG retrieval", value: 91, status: "healthy" },
  { label: "Semantic cache", value: 74, status: "warming" }
];

const jobs = [
  {
    title: "Post-surgery companion care",
    city: "Shanghai",
    patient: "Elderly patient, hip recovery",
    budget: "480 CNY/day",
    status: "Matching",
    applicants: 18
  },
  {
    title: "Night-shift ward companion",
    city: "Hangzhou",
    patient: "Respiratory monitoring",
    budget: "360 CNY/day",
    status: "Interviewing",
    applicants: 9
  },
  {
    title: "Home rehabilitation support",
    city: "Suzhou",
    patient: "Stroke rehab assistance",
    budget: "520 CNY/day",
    status: "Published",
    applicants: 24
  }
];

const verifications = [
  { name: "Lin Yue", role: "Caregiver", stage: "Credential review", score: 92 },
  { name: "Chen Hao", role: "Nurse assistant", stage: "Identity check", score: 87 },
  { name: "Wang Min", role: "Family employer", stage: "Phone verification", score: 99 }
];

const collections = [
  { name: "medical.symptom_inquiry", chunks: 1260, freshness: "Today", source: "Demo crawler" },
  { name: "medical.medication_consult", chunks: 860, freshness: "Today", source: "Demo crawler" },
  { name: "medical.report_interpretation", chunks: 540, freshness: "Yesterday", source: "Curated demo" },
  { name: "medical.care_method", chunks: 720, freshness: "Today", source: "Care guideline demo" },
  { name: "platform.recruitment_process", chunks: 160, freshness: "Stable", source: "Internal FAQ" }
];

const systemServices = [
  { name: "backend", port: 8000, status: "Ready", detail: "FastAPI business gateway" },
  { name: "ai-service", port: 8100, status: "Ready", detail: "Intent routing and response orchestration" },
  { name: "embedding-service", port: 8200, status: "Ready", detail: "BGE-compatible embeddings" },
  { name: "postgres + pgvector", port: 5432, status: "Configured", detail: "Primary data and vector storage" },
  { name: "redis", port: 6379, status: "Configured", detail: "L2 cache and session state" },
  { name: "minio", port: 9000, status: "Configured", detail: "Object storage for documents" }
];

function App() {
  const [activeView, setActiveView] = useState<View>("overview");
  const activeLabel = navItems.find((item) => item.id === activeView)?.label ?? "Overview";

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">
            <HeartPulse size={24} />
          </div>
          <div>
            <strong>DoctorCarePlatform</strong>
            <span>AI care operations</span>
          </div>
        </div>

        <nav className="navList" aria-label="Primary navigation">
          {navItems.map((item) => (
            <button
              className={activeView === item.id ? "active" : ""}
              key={item.id}
              onClick={() => setActiveView(item.id)}
              type="button"
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebarStatus">
          <span className="statusDot" />
          <div>
            <strong>Demo environment</strong>
            <span>All core services verified locally</span>
          </div>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Development Console</p>
            <h1>{activeLabel}</h1>
          </div>
          <div className="topbarActions">
            <button className="iconButton" title="Notifications" type="button">
              <Bell size={19} />
            </button>
            <button className="iconButton" title="Verification status" type="button">
              <BadgeCheck size={19} />
            </button>
          </div>
        </header>

        {activeView === "overview" && <Overview />}
        {activeView === "consultation" && <Consultation />}
        {activeView === "jobs" && <Jobs />}
        {activeView === "verification" && <Verification />}
        {activeView === "knowledge" && <Knowledge />}
        {activeView === "settings" && <SystemSettings />}
      </section>
    </main>
  );
}

function Overview() {
  return (
    <>
      <section className="metrics">
        {metrics.map((metric) => (
          <article className={`metric ${metric.tone}`} key={metric.label}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <small>{metric.detail}</small>
          </article>
        ))}
      </section>

      <section className="dashboardGrid">
        <article className="panel wide">
          <div className="panelHeader">
            <div>
              <h2>Clinical AI Flow</h2>
              <p>From safety filtering to intent routing, retrieval, and response assembly.</p>
            </div>
            <Sparkles size={22} />
          </div>
          <div className="flowLine">
            {["Emergency", "Classify", "Retrieve", "Generate", "Audit"].map((step, index) => (
              <div className="flowStep" key={step}>
                <span>{index + 1}</span>
                <strong>{step}</strong>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <div className="panelHeader compact">
            <h2>Pipeline Health</h2>
            <Activity size={20} />
          </div>
          <div className="progressList">
            {pipelines.map((item) => (
              <div className="progressItem" key={item.label}>
                <div>
                  <strong>{item.label}</strong>
                  <span>{item.status}</span>
                </div>
                <meter max="100" value={item.value} />
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <div className="panelHeader compact">
            <h2>Today</h2>
            <CalendarClock size={20} />
          </div>
          <ul className="eventList">
            <li>12 caregiver interviews scheduled</li>
            <li>8 urgent AI consultations reviewed</li>
            <li>34 new knowledge chunks indexed</li>
            <li>6 SMS templates waiting for approval</li>
          </ul>
        </article>
      </section>
    </>
  );
}

function Consultation() {
  const [message, setMessage] = useState("How often should this medication be taken, and what are the side effects?");
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submitConsultation() {
    setLoading(true);
    setError("");
    try {
      const result = await fetch("/api/v1/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message })
      });
      if (!result.ok) {
        throw new Error(`API returned ${result.status}`);
      }
      setResponse(await result.json());
    } catch {
      setResponse({
        answer:
          "Demo fallback: the local backend is not connected from this page, but the consultation interface is ready. Start backend on port 8000 or use docker compose for live responses.",
        intent: { category: "medical_consult", subcategory: "medication_consult", confidence: 0.95 },
        cache_hit_level: "demo",
        citations: [
          {
            title: "Medication safety",
            snippet: "Medication questions are routed to the medication_consult collection."
          }
        ]
      });
      setError("Using built-in demo response because the API request was not reachable.");
    } finally {
      setLoading(false);
    }
  }

  const confidencePercent = useMemo(
    () => Math.round((response?.intent.confidence ?? 0) * 100),
    [response]
  );

  return (
    <section className="consultationLayout">
      <article className="panel">
        <div className="panelHeader">
          <div>
            <h2>AI Consultation Sandbox</h2>
            <p>Submit a patient or platform question and inspect the routed intent.</p>
          </div>
          <Stethoscope size={22} />
        </div>

        <label className="fieldLabel" htmlFor="consultationInput">
          User message
        </label>
        <textarea
          id="consultationInput"
          onChange={(event) => setMessage(event.target.value)}
          value={message}
        />
        <div className="buttonRow">
          <button className="primaryButton" disabled={loading || !message.trim()} onClick={submitConsultation}>
            {loading ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
            <span>{loading ? "Routing..." : "Run Consultation"}</span>
          </button>
          <button
            className="secondaryButton"
            onClick={() => setMessage("How can caregivers prevent pressure injuries after surgery?")}
            type="button"
          >
            Care example
          </button>
        </div>
        {error && <p className="notice">{error}</p>}
      </article>

      <article className="panel resultPanel">
        <div className="panelHeader compact">
          <h2>Response</h2>
          <ClipboardList size={20} />
        </div>
        {response ? (
          <>
            <p className="answerText">{response.answer}</p>
            <div className="intentGrid">
              <div>
                <span>Category</span>
                <strong>{response.intent.category}</strong>
              </div>
              <div>
                <span>Subcategory</span>
                <strong>{response.intent.subcategory || "none"}</strong>
              </div>
              <div>
                <span>Confidence</span>
                <strong>{confidencePercent}%</strong>
              </div>
              <div>
                <span>Cache</span>
                <strong>{response.cache_hit_level}</strong>
              </div>
            </div>
            <div className="citationList">
              {response.citations.map((citation) => (
                <div key={`${citation.title}-${citation.snippet}`}>
                  <strong>{citation.title || "Context"}</strong>
                  <span>{citation.snippet}</span>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="emptyState">
            <MessageSquareText size={28} />
            <p>Run a consultation to see the intent, cache level, answer, and citations.</p>
          </div>
        )}
      </article>
    </section>
  );
}

function Jobs() {
  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <h2>Caregiver Matching Board</h2>
          <p>Operational view for published care jobs and candidate matching progress.</p>
        </div>
        <BriefcaseMedical size={22} />
      </div>
      <div className="tableLike">
        {jobs.map((job) => (
          <article className="rowCard" key={job.title}>
            <div>
              <strong>{job.title}</strong>
              <span>{job.city} / {job.patient}</span>
            </div>
            <div>
              <span>Budget</span>
              <strong>{job.budget}</strong>
            </div>
            <div>
              <span>Applicants</span>
              <strong>{job.applicants}</strong>
            </div>
            <span className="pill">{job.status}</span>
          </article>
        ))}
      </div>
    </section>
  );
}

function Verification() {
  return (
    <section className="dashboardGrid">
      <article className="panel wide">
        <div className="panelHeader">
          <div>
            <h2>Verification Queue</h2>
            <p>Review caregiver credentials, identity checks, and employer onboarding.</p>
          </div>
          <ShieldCheck size={22} />
        </div>
        <div className="verificationGrid">
          {verifications.map((item) => (
            <div className="verificationCard" key={item.name}>
              <div className="avatar">{item.name.slice(0, 1)}</div>
              <div>
                <strong>{item.name}</strong>
                <span>{item.role}</span>
              </div>
              <div>
                <span>{item.stage}</span>
                <meter max="100" value={item.score} />
              </div>
            </div>
          ))}
        </div>
      </article>

      <article className="panel">
        <div className="panelHeader compact">
          <h2>Controls</h2>
          <CheckCircle2 size={20} />
        </div>
        <ul className="eventList">
          <li>Phone verification via Aliyun SMS adapter</li>
          <li>Manual document review hooks</li>
          <li>Audit trail ready for admin logs</li>
        </ul>
      </article>
    </section>
  );
}

function Knowledge() {
  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <h2>RAG Knowledge Collections</h2>
          <p>Each intent subcategory maps to an isolated retrieval namespace.</p>
        </div>
        <Database size={22} />
      </div>
      <div className="collectionGrid">
        {collections.map((collection) => (
          <article className="collectionCard" key={collection.name}>
            <BookOpenCheck size={20} />
            <strong>{collection.name}</strong>
            <span>{collection.chunks.toLocaleString()} chunks</span>
            <small>{collection.freshness} / {collection.source}</small>
          </article>
        ))}
      </div>
    </section>
  );
}

function SystemSettings() {
  return (
    <section className="dashboardGrid">
      <article className="panel wide">
        <div className="panelHeader">
          <div>
            <h2>Service Topology</h2>
            <p>Docker Compose services and local development ports.</p>
          </div>
          <Settings size={22} />
        </div>
        <div className="serviceGrid">
          {systemServices.map((service) => (
            <div className="serviceItem" key={service.name}>
              <div>
                <strong>{service.name}</strong>
                <span>{service.detail}</span>
              </div>
              <div>
                <small>:{service.port}</small>
                <span className="pill greenPill">{service.status}</span>
              </div>
            </div>
          ))}
        </div>
      </article>

      <article className="panel">
        <div className="panelHeader compact">
          <h2>Launch</h2>
          <FileHeart size={20} />
        </div>
        <div className="commandBox">
          <code>docker compose up --build</code>
        </div>
        <div className="searchBox">
          <Search size={18} />
          <span>Open http://localhost:3000</span>
        </div>
      </article>
    </section>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
