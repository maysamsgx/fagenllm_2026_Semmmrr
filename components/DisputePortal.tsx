import React, { useEffect, useState } from 'react';
import { MessageSquare, CheckCircle, XCircle, User, Calendar, ExternalLink } from 'lucide-react';
import { Card } from './Shared';

const DisputePortal: React.FC = () => {
    const [disputes, setDisputes] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch('http://localhost:8000/api/analytics/disputes')
            .then(res => res.json())
            .then(data => {
                setDisputes(data);
                setLoading(false);
            });
    }, []);

    const resolveDispute = (id: string) => {
        setDisputes(prev => prev.filter((d: any) => d.id !== id));
    };

    if (loading) return <Card className="p-8"><div className="text-white/50 animate-pulse text-sm">Loading Disputes...</div></Card>;

    return (
        <Card className="animate-in fade-in duration-500 flex flex-col" style={{ minHeight: '100%' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <MessageSquare size={16} style={{ color: 'var(--cyan)' }} />
                    Dispute Portal
                </h3>
                <span style={{ fontSize: 11, color: 'var(--text-4)', fontWeight: 500 }}>{disputes.length} active</span>
            </div>

            {disputes.length === 0 ? (
                <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: 0.5, fontStyle: 'italic', fontSize: 13 }}>
                    No active disputes.
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {disputes.map((dispute: any) => (
                        <div key={dispute.id} style={{
                            background: 'rgba(255,255,255,0.03)',
                            border: '1px solid rgba(255,255,255,0.06)',
                            borderRadius: 10,
                            padding: '12px 14px',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            transition: 'all 0.2s',
                        }} className="group hover:bg-white/5 hover:border-white/10">
                            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                                <div style={{
                                    width: 32, height: 32, borderRadius: '50%', background: 'rgba(255,255,255,0.05)',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-4)'
                                }}>
                                    <User size={16} />
                                </div>
                                <div>
                                    <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)', display: 'flex', alignItems: 'center', gap: 8 }}>
                                        {dispute.customer_name}
                                        <span style={{
                                            fontSize: 9, padding: '2px 6px', borderRadius: 999, textTransform: 'uppercase', letterSpacing: '0.05em',
                                            background: dispute.collection_stage === 'escalated' ? 'rgba(251,113,133,0.15)' : 'rgba(34,211,238,0.15)',
                                            color: dispute.collection_stage === 'escalated' ? 'var(--rose)' : 'var(--cyan)'
                                        }}>
                                            {dispute.collection_stage}
                                        </span>
                                    </div>
                                    <div style={{ fontSize: 11, color: 'var(--text-4)', display: 'flex', gap: 12, marginTop: 4 }}>
                                        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><Calendar size={10}/> {dispute.due_date}</span>
                                        <span style={{ color: 'var(--emerald)', fontWeight: 500 }}>${dispute.amount.toLocaleString()}</span>
                                    </div>
                                </div>
                            </div>

                            <div style={{ display: 'flex', gap: 4, opacity: 0, transition: 'opacity 0.2s' }} className="group-hover:opacity-100">
                                <button 
                                    onClick={() => resolveDispute(dispute.id)}
                                    style={{ background: 'rgba(52,211,153,0.15)', color: 'var(--emerald)', border: 'none', padding: 6, borderRadius: 6, cursor: 'pointer' }}
                                    title="Resolve"
                                ><CheckCircle size={14} /></button>
                                <button 
                                    style={{ background: 'rgba(251,113,133,0.15)', color: 'var(--rose)', border: 'none', padding: 6, borderRadius: 6, cursor: 'pointer' }}
                                    title="Escalate"
                                ><XCircle size={14} /></button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </Card>
    );
};

export default DisputePortal;
