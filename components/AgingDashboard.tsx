import React, { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Clock, TrendingUp, DollarSign, AlertCircle } from 'lucide-react';
import { Card } from './Shared';

const AGING_COLORS = ['#22d3ee', '#6366f1', '#a78bfa', '#e879f9', '#fb7185'];

export function useAnalytics() {
    const [agingData, setAgingData] = useState([]);
    const [metrics, setMetrics] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [agingRes, metricsRes] = await Promise.all([
                    fetch('http://localhost:8000/api/analytics/aging'),
                    fetch('http://localhost:8000/api/analytics/performance')
                ]);
                setAgingData(await agingRes.json());
                setMetrics(await metricsRes.json());
            } catch (error) {
                console.error("Failed to fetch analytics", error);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    return { agingData, metrics, loading };
}

export const AgingMetricsRow: React.FC<{ metrics: any, loading: boolean }> = ({ metrics, loading }) => {
    if (loading) return <div className="stats-row animate-pulse"><Card className="h-24"></Card><Card></Card><Card></Card><Card></Card></div>;
    return (
        <div className="stats-row">
            <MetricCard
                title="DSO (Days)"
                value={metrics?.dso}
                icon={<Clock size={20} className="text-cyan-400" />}
                desc="Days Sales Outstanding"
            />
            <MetricCard
                title="Recovery Rate"
                value={`${metrics?.recovery_rate}%`}
                icon={<TrendingUp size={20} className="text-emerald-400" />}
                desc="Collection Efficiency"
            />
            <MetricCard
                title="Total Collected"
                value={`$${(metrics?.collected_amount / 1000).toFixed(1)}k`}
                icon={<DollarSign size={20} className="text-indigo-400" />}
                desc="Total Cash Inflow"
            />
            <MetricCard
                title="Total AR"
                value={`$${(metrics?.total_receivables / 1000).toFixed(1)}k`}
                icon={<AlertCircle size={20} className="text-amber-400" />}
                desc="Gross Receivables"
            />
        </div>
    );
};

export const AgingChartCard: React.FC<{ agingData: any, loading: boolean }> = ({ agingData, loading }) => {
    if (loading) return <Card className="h-64 animate-pulse"></Card>;

    return (
        <Card className="flex flex-col h-full">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <h3 style={{ margin: 0, fontSize: 14, letterSpacing: '0.02em', textTransform: 'uppercase', color: 'var(--text-3)' }}>
                    AR Aging Profile
                </h3>
            </div>
            <div style={{ height: 250, width: '100%' }}>
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={agingData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="2 4" stroke="rgba(255,255,255,.03)" vertical={false} />
                        <XAxis
                            dataKey="name"
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: '#8891b3', fontSize: 10, fontFamily: "'Space Grotesk', sans-serif" }}
                        />
                        <YAxis
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: '#5b6486', fontSize: 10, fontFamily: "'Space Grotesk', sans-serif" }}
                            tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
                        />
                        <Tooltip
                            cursor={{ fill: 'rgba(255,255,255,.02)', rx: 4 }}
                            contentStyle={{
                                backgroundColor: 'rgba(10,14,30,.97)',
                                border: '1px solid rgba(34,211,238,.15)',
                                borderRadius: '8px',
                                backdropFilter: 'blur(16px)',
                                boxShadow: '0 8px 32px rgba(0,0,0,0.6)'
                            }}
                            itemStyle={{ color: '#fff', fontFamily: "'JetBrains Mono', monospace", fontWeight: 500, fontSize: 13 }}
                        />
                        <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={28}>
                            {agingData.map((entry: any, index: number) => (
                                <Cell key={`cell-${index}`} fill={AGING_COLORS[index % AGING_COLORS.length]} />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </Card>
    );
};

const MetricCard = ({ title, value, icon, desc }: any) => (
    <Card className="relative overflow-hidden group hover:border-cyan-500/30 transition-all duration-300">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
            <span className="stat-label" style={{ margin: 0, color: 'var(--text-4)' }}>{title}</span>
            <div style={{ padding: 6, borderRadius: 8, background: 'rgba(255,255,255,0.03)', boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.05)' }} className="group-hover:bg-white/10 group-hover:scale-110 transition-all duration-300">
                {icon}
            </div>
        </div>
        <div className="stat-value" style={{ textShadow: '0 0 20px rgba(255,255,255,0.1)' }}>{value}</div>
        <div style={{ fontSize: 10, color: 'var(--text-4)', marginTop: 6, display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--cyan)', opacity: 0.5 }}></span>
            {desc}
        </div>

        {/* Decorative background glow */}
        <div style={{
            position: 'absolute', right: -20, bottom: -20, width: 100, height: 100,
            background: 'radial-gradient(circle, rgba(34,211,238,0.1) 0%, transparent 70%)',
            pointerEvents: 'none'
        }} className="opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
    </Card>
);

