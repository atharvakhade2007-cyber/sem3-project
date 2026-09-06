import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, LineChart,
  Line, BarChart, Bar, Cell
} from 'recharts';

const DIFFICULTY_COLORS = {
  easy: '#10b981',
  medium: '#f59e0b',
  hard: '#ef4444',
};

const TIER_COLORS = {
  Beginner: '#10b981',
  Intermediate: '#f59e0b',
  Advanced: '#ef4444',
};

function StatCard({ icon, label, value, sub }) {
  return (
    <div style={{
      background: 'var(--card-bg)', border: '1px solid var(--card-border)',
      borderRadius: 14, padding: '1rem 1.1rem', textAlign: 'center',
    }}>
      <div style={{ fontSize: '1.35rem', marginBottom: '0.2rem' }}>{icon}</div>
      <div style={{ fontSize: '1.5rem', fontWeight: 800, lineHeight: 1.1 }}>{value}</div>
      <div style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', marginTop: '0.25rem' }}>
        {label}
      </div>
      {sub && (
        <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem', marginTop: '0.15rem' }}>
          {sub}
        </div>
      )}
    </div>
  );
}

function TierProgressRing({ current, next, pct, points }) {
  const color = TIER_COLORS[current] || '#6366f1';
  const size = 120;
  const stroke = 10;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size / 2} cy={size / 2} r={radius} stroke="var(--card-border)" strokeWidth={stroke} fill="none" />
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          stroke={color} strokeWidth={stroke} fill="none"
          strokeDasharray={circumference} strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.8s ease' }}
        />
        <text x={size / 2} y={size / 2 - 4} textAnchor="middle" fill="var(--text)" fontSize="1.1rem" fontWeight={700}>
          {pct.toFixed(0)}%
        </text>
        <text x={size / 2} y={size / 2 + 14} textAnchor="middle" fill="var(--text-muted)" fontSize="0.7rem">
          to {next}
        </text>
      </svg>
      <div>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Current Tier
        </div>
        <div style={{ fontSize: '1.1rem', fontWeight: 700, color: color, marginTop: '0.2rem' }}>
          {current}
        </div>
        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.4rem' }}>
          {points} pts to next
        </div>
      </div>
    </div>
  );
}

export default function StudentAnalyticsDashboard({ analytics, loading, onRefresh }) {
  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
        <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📊</div>
        <div style={{ fontSize: '0.9rem' }}>Loading your analytics…</div>
        {onRefresh && (
          <button onClick={onRefresh} style={{
            marginTop: '1rem',
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            color: '#fff', border: 'none',
            borderRadius: 8, padding: '0.5rem 1.2rem',
            fontWeight: 600, cursor: 'pointer', fontSize: '0.85rem',
          }}>
            Retry
          </button>
        )}
      </div>
    );
  }

  if (!analytics) return null;

  const { summary, difficulty_breakdown, radar_archetype, time_series_history, recent_quizzes } = analytics;

  const diffData = [
    { name: 'Easy', attempted: difficulty_breakdown.easy?.attempted ?? 0, accuracy: difficulty_breakdown.easy?.accuracy ?? 0, color: DIFFICULTY_COLORS.easy },
    { name: 'Medium', attempted: difficulty_breakdown.medium?.attempted ?? 0, accuracy: difficulty_breakdown.medium?.accuracy ?? 0, color: DIFFICULTY_COLORS.medium },
    { name: 'Hard', attempted: difficulty_breakdown.hard?.attempted ?? 0, accuracy: difficulty_breakdown.hard?.accuracy ?? 0, color: DIFFICULTY_COLORS.hard },
  ];

  const radarData = radar_archetype.map(r => ({
    ...r,
    student: Number.isFinite(r.student) ? r.student : 0,
    cohort_average: Number.isFinite(r.cohort_average) ? r.cohort_average : 0,
  }));

  const tsData = time_series_history.map(t => ({
    ...t,
    elo: Number.isFinite(t.elo) ? t.elo : 0,
    accuracy: Number.isFinite(t.accuracy) ? t.accuracy : 0,
  }));

  return (
    <div>
      {/* ═══ Summary Card Row ═══ */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
        gap: '1rem',
        marginBottom: '2rem',
      }}>
        <StatCard icon="🎓" label="Student Level" value={summary.student_level} />
        <StatCard icon="🤖" label="ML Confidence" value={`${summary.ml_confidence?.toFixed(1)}%`} />
        <StatCard icon="⚡" label="Current Elo" value={summary.current_elo?.toFixed(0)} />
        <StatCard icon="📈" label="Elo Δ 7d" value={summary.elo_change_last_7_days >= 0 ? `+${summary.elo_change_last_7_days?.toFixed(0)}` : summary.elo_change_last_7_days?.toFixed(0)} sub={summary.elo_change_last_7_days !== 0 ? (summary.elo_change_last_7_days > 0 ? 'up' : 'down') : 'stable'} />
        <StatCard icon="🎯" label="Overall Accuracy" value={`${summary.overall_accuracy?.toFixed(1)}%`} />
        <StatCard icon="❓" label="Questions Attempted" value={summary.questions_attempted?.toFixed(0)} />
        <StatCard icon="⏱️" label="Avg Response Time" value={`${summary.avg_response_time_seconds?.toFixed(1)}s`} />
        <StatCard icon="🔥" label="Current Streak" value={summary.current_streak?.toFixed(0)} sub={`Best: ${summary.longest_streak?.toFixed(0)}`} />
      </div>

      {/* ═══ Tier Progression ═══ */}
      <div style={{
        background: 'var(--card-bg)', border: '1px solid var(--card-border)',
        borderRadius: 16, padding: '1.25rem 1.5rem', marginBottom: '2rem',
      }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '1rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Tier Progression
        </h3>
        <TierProgressRing
          current={summary.tier_progression?.current_tier}
          next={summary.tier_progression?.next_tier}
          pct={summary.tier_progression?.progress_percentage}
          points={summary.tier_progression?.points_to_next_tier}
        />
      </div>

      {/* ═══ Charts Row: Difficulty + Radar ═══ */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '1.5rem',
        marginBottom: '2rem',
      }}>
        {/* Difficulty Breakdown Bar Chart */}
        <div style={{
          background: 'var(--card-bg)', border: '1px solid var(--card-border)',
          borderRadius: 16, padding: '1.25rem 1.5rem',
        }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '1rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Difficulty Breakdown
          </h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={diffData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="var(--card-border)" />
              <XAxis type="number" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
              <YAxis dataKey="name" type="category" width={50} tick={{ fill: 'var(--text)', fontSize: 12 }} />
              <Tooltip
                contentStyle={{
                  background: 'rgba(15,23,42,0.95)',
                  border: '1px solid var(--card-border)',
                  borderRadius: 8,
                  color: 'var(--text)',
                  fontSize: '0.8rem',
                }}
                formatter={(value, name) => {
                  if (name === 'accuracy') return [`${value?.toFixed(1)}%`, 'Accuracy'];
                  return [value?.toFixed(0), 'Attempted'];
                }}
              />
              <Bar dataKey="attempted" fill="#6366f1" radius={[0, 4, 4, 0]} name="Attempted" stackId="a" />
              <Bar dataKey="accuracy" fill="var(--text-muted)" radius={[0, 4, 4, 0]} name="Accuracy" stackId="a" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Radar Archetype */}
        <div style={{
          background: 'var(--card-bg)', border: '1px solid var(--card-border)',
          borderRadius: 16, padding: '1.25rem 1.5rem',
        }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '1rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Student Radar vs Cohort
          </h3>
          <ResponsiveContainer width="100%" height={280}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="var(--card-border)" />
              <PolarAngleAxis dataKey="subject" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
              <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
              <Radar
                dataKey="student"
                stroke="#6366f1"
                fill="#6366f1"
                fillOpacity={0.3}
                strokeWidth={2}
                name="You"
              />
              <Radar
                dataKey="cohort_average"
                stroke="var(--text-muted)"
                fill="var(--text-muted)"
                fillOpacity={0.15}
                strokeWidth={1.5}
                strokeDasharray="4 4"
                name="Cohort"
              />
              <Tooltip
                contentStyle={{
                  background: 'rgba(15,23,42,0.95)',
                  border: '1px solid var(--card-border)',
                  borderRadius: 8,
                  color: 'var(--text)',
                  fontSize: '0.8rem',
                }}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ═══ Time Series History ═══ */}
      <div style={{
        background: 'var(--card-bg)', border: '1px solid var(--card-border)',
        borderRadius: 16, padding: '1.25rem 1.5rem', marginBottom: '2rem',
      }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '1rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Elo & Accuracy History
        </h3>
        {tsData.length > 0 ? (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={tsData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--card-border)" />
              <XAxis dataKey="date" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
              <YAxis yAxisId="left" domain={['auto', 'auto']} tick={{ fill: '#6366f1', fontSize: 11 }} />
              <YAxis yAxisId="right" orientation="right" domain={[0, 100]} tick={{ fill: '#f59e0b', fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  background: 'rgba(15,23,42,0.95)',
                  border: '1px solid var(--card-border)',
                  borderRadius: 8,
                  color: 'var(--text)',
                  fontSize: '0.8rem',
                }}
              />
              <Line yAxisId="left" type="monotone" dataKey="elo" stroke="#6366f1" strokeWidth={2} dot={{ fill: '#6366f1', r: 3 }} name="Elo" />
              <Line yAxisId="right" type="monotone" dataKey="accuracy" stroke="#f59e0b" strokeWidth={2} dot={{ fill: '#f59e0b', r: 3 }} name="Accuracy %" />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            No session history yet — start your first adaptive quiz to see trends.
          </div>
        )}
      </div>

      {/* ═══ Recent Quizzes Table ═══ */}
      <div style={{
        background: 'var(--card-bg)', border: '1px solid var(--card-border)',
        borderRadius: 16, padding: '1.25rem 1.5rem',
      }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '1rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Recent Quizzes
        </h3>
        {recent_quizzes.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--card-border)' }}>
                  <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Topic</th>
                  <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Date</th>
                  <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Score</th>
                  <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Accuracy</th>
                  <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Elo Δ</th>
                  <th style={{ textAlign: 'left', padding: '0.5rem 0.75rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Time</th>
                </tr>
              </thead>
              <tbody>
                {recent_quizzes.map(q => (
                  <tr key={q.session_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                    <td style={{ padding: '0.5rem 0.75rem', color: 'var(--text)', fontWeight: 500 }}>{q.topic}</td>
                    <td style={{ padding: '0.5rem 0.75rem', color: 'var(--text-secondary)' }}>{q.date}</td>
                    <td style={{ padding: '0.5rem 0.75rem', color: 'var(--text)' }}>{q.score}</td>
                    <td style={{ padding: '0.5rem 0.75rem', color: 'var(--text)' }}>{q.accuracy?.toFixed(1)}%</td>
                    <td style={{ padding: '0.5rem 0.75rem', color: q.elo_delta?.startsWith('+') ? '#10b981' : '#ef4444', fontWeight: 600 }}>{q.elo_delta}</td>
                    <td style={{ padding: '0.5rem 0.75rem', color: 'var(--text-secondary)' }}>{q.time_taken}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            No completed quizzes yet.
            {onRefresh && (
              <button onClick={onRefresh} style={{
                marginTop: '1rem',
                background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                color: '#fff', border: 'none',
                borderRadius: 8, padding: '0.5rem 1.2rem',
                fontWeight: 600, cursor: 'pointer', fontSize: '0.85rem',
              }}>
                Refresh Analytics
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
