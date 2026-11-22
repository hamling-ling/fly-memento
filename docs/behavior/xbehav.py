"""Research snapshot. Not imported by the robot or the simulator.

The runnable memory rules are `brain/memory.py`. This file is the fuller
T-maze model and still imports the connectome package (`pm`) used during
the research pass, which is not in this repository.

"""
"""Cross-scale model: connectome -> circuit (PPL1 oscillation states, circuit_states.csv) -> memory traces -> MBON ensemble -> T-maze PI.
ALL memory/behaviour-layer forms and constants are ASSUMPTIONS (labelled A#); qualitative directions are compared to literature.
Time unit: minutes.
A1 circuit state timeline (imposed from Placais 2012 imaging, not derived): after 1x or each spaced cycle -> 'on' (oscillating);
    after massed (inter-cycle gaps <10 min) -> 'weak' = bias -0.5 state (56% of sets still oscillate; cf. Placais massed 4/11 osc, 3/11 quiet).
A2 DA signals from MP1/MV1: forgetting drive F (Berry 2012) = mean rectified activity (A101+A103)/2; ARM-inhibition drive Z = slow (tau_z=30 min)
    low-pass of either ADD=(A101+A103)/2 or COI=C=<r101*r103> coincidence (time-averaged product, rewards synchrony) (two variants), normalised to the WT 'on' median.
A3 traces per PPL1 compartment c (g1pedc<-PPL101, g2a'1<-PPL103, a'2a2<-PPL105): labile S (+eta(1-S) per cycle; decay kS+kF*F_c),
    ARM A (conversion from S at kA*S/(1+Z/th)/(1+L/thL) [exclusivity, Placais], decay kAd, erased by DA during spaced ITIs kE*Z*A), LTM L (forms only during rest gaps >=10 min [spacing gate],
    rate kL*S*Z/(Z+th) with instantaneous Z within the first 10 min of each ITI [Placais Fig 7], slow decay; CXM -> L=0).
A4 readout: KC->MBON weight for CS+ u_m = 1 - delta*sum_c A_MD[m,c]*M_c (A_MD = male-CNS compartment overlap); MBON steady state with
    MBON-MBON wiring JMM (gmm=1); valence v_m = -1 glu, +1 ACh/GABA (Aso 2014b rule) for MBON01-22, 0 for atypical MBONs;
    PI = 100*tanh(beta*Delta), Delta = -sum v_m (m_m(CS+)-1); beta fixed so WT 1x immediate PI = 80 (arbitrary scale)."""
import numpy as np,pandas as pd,sys
sys.path.insert(0,'/workspace/mb-oscillation/mbon_dan/placais'); import pm
P=dict(eta=0.5,kS=1/60,kF=1/60,kA=1/30,th=0.5,thL=0.2,kAd=1/(48*60),kL=1/20,kE=1/5,kLd=1/(7*24*60),delta=0.8,tau_z=30.,trp=30.0,win=10.)
import os as _os; CS=pd.read_csv(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),'circuit_states.csv'))
def norm_stats(df):
    on=df[df.state=='on']; return dict(F=np.median((on.A101+on.A103)/2), ADD=np.median((on.A101+on.A103)/2), COI=np.median(on.C))
NS=norm_stats(CS)
def sigs(row,variant):
    F101=row.A101/NS['F']; F103=row.A103/NS['F']; F105=row.A105/NS['F']
    Z=((row.A101+row.A103)/2/NS['ADD']) if variant=='ADD' else (row.C/NS['COI'])
    return np.array([F101,F103,F105]),Z
def protocol(name):
    """returns list of cycle start times (min) and post-training state name"""
    if name=='1x': return [0.],'on'
    if name=='massed': return [i*2. for i in range(5)],'weak'      # 1-min cycles, 1-min gaps
    if name=='massed5': return [i*6. for i in range(5)],'weak'     # 5-min ITI (Placais Fig 5c)
    if name=='spaced': return [i*16. for i in range(5)],'on'       # 15-min ITI
def simulate(sig_on,Z_on,sig_weak,Z_weak,prot,T_test,manip=None,p=P,dt=0.5):
    cyc,post=protocol(prot); t_end=cyc[-1]+1; n=int((t_end+T_test)/dt)
    S=np.zeros(3); A=np.zeros(3); L=np.zeros(3); Zs=0.
    for i in range(n):
        t=i*dt
        for c0 in cyc:
            if abs(t-c0)<dt/2: S=S+p['eta']*(1-S)
        in_train=any(c0<=t<c0+1 for c0 in cyc)
        prev=[c0 for c0 in cyc if c0+1<=t]; nxt=[c0 for c0 in cyc if c0>t]
        gap=(min(nxt)-(max(prev)+1)) if (prev and nxt) else None
        in_rest=gap is not None and gap>=10.                         # spacing gate
        st_post=post if (t>=t_end or prot=='spaced') else post
        F,Z=(sig_on,Z_on) if st_post=='on' else (sig_weak,Z_weak)
        if prot in('massed','massed5') and t<t_end: F,Z=sig_on,Z_on # during massed cycles themselves treat as on
        fmul=1.; 
        if manip:
            for kind,a,b in manip:
                ta=a if a>=0 else None
                if kind=='block' and a<=t<b: fmul=0.
                if kind=='block_iti' and in_rest and any(c0+1<=t<c0+1+8 for c0 in cyc): fmul=0.
                if kind=='trp' and any(c0+1<=t<c0+2 for c0 in cyc) and a<=t<b: fmul=p['trp']
                if kind=='trp_after_end' and t_end<=t<t_end+1: fmul=p['trp']
        Fx=F*fmul; Zin=Z*fmul
        Zs+=dt/p['tau_z']*(Zin-Zs)
        conv=p['kA']*S/(1+Zs/p['th'])/(1+L.mean()/p['thL'])          # S -> ARM conversion, inhibited by DA (Placais) & LTM (exclusivity)
        dS=-(p['kS']+p['kF']*Fx)*S-conv
        dA=conv-p['kAd']*A-(p['kE']*Zs*A if in_rest else 0.)            # ARM erased by DA during spaced ITIs (A, assumption)
        early=in_rest and any(c0+1<=t<c0+1+p['win'] for c0 in cyc)       # LTM induction window = first 10 min of ITI (assumption motivated by P7)
        dL=(p['kL']*S*Zin/(Zin+p['th']) if early else 0.)-p['kLd']*L
        if manip and ('cxm',0,0) in manip: dL=0*dL; L=L*0
        if not in_train: S=S+dt*dS
        A=A+dt*dA; L=L+dt*dL
    return dict(S=S,A=A,L=L,M=np.minimum(1,S+A+L))
# ---- readout
iC=[pm.iD['PPL101'],pm.iD['PPL103'],pm.iD['PPL105']]
def valence(atyp=False):
    v=np.where(pm.NTM=='glu',-1.,np.where(np.isin(pm.NTM,['ach','gaba']),1.,0.))
    if not atyp:
        num=np.array([int(''.join(ch for ch in m[4:6] if ch.isdigit()) or 99) for m in pm.MT]); v=np.where(num<=22,v,0.)
    return v
def readout(M,s_glu=-1.,JMM=None,AMD=None,v=None,gmm=1.,p=P):
    AM=pm.T['A_MD'] if AMD is None else AMD; v=valence() if v is None else v
    _,_,_,_,_,J=pm.mats(s_glu) if JMM is None else (None,)*5+(JMM,)
    u=1-p['delta']*np.clip(AM[:,iC]@M,0,1)
    m=np.ones(pm.nm)
    for _ in range(200): m=m+0.2*(-m+pm.sat(u+gmm*((m-1)@J.T),5.))
    return -float(v@(m-1))
