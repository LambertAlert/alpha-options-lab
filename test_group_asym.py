import math, time, numpy as np, pandas as pd
import group_asym as ga
R={"pass":0,"fail":0}
def ok(c,msg): R["pass" if c else "fail"]+=1; print(("PASS " if c else "FAIL ")+msg)

# RS rating by hand
idx=pd.bdate_range("2020-01-01",periods=300)
c=pd.DataFrame({t: 100*np.exp(np.linspace(0,k,300)) for t,k in zip("ABCD",[-.2,0,.3,.6])},index=idx)
rs=ga.rs_rating(c)
ok(rs.iloc[:252].isna().all().all() and list(rs.iloc[-1])==[25,50,75,99], f"RS rating ranks 1-99 ({list(rs.iloc[-1])})")

# planted groups: 4 groups x 6 names; group G0 strong, G3 weak
rng=np.random.default_rng(0); n=600; idx=pd.bdate_range("2023-01-02",periods=n)
groups={}; P={k:{} for k in ("open","high","low","close","volume")}
for gi,drift in enumerate([0.003,0.0008,0.0,-0.0012]):
    for j in range(10):
        t=f"G{gi}N{j}"; groups[t]=f"Grp{gi}"
        r=drift+rng.normal(0,0.012,n); cl=50*np.exp(np.cumsum(r)); op=np.r_[50,cl[:-1]]
        P["close"][t]=cl; P["open"][t]=op; P["high"][t]=np.maximum(op,cl)*1.006; P["low"][t]=np.minimum(op,cl)*0.994; P["volume"][t]=np.full(n,1e6)
groups["LONER"]="Solo"; cl=50*np.exp(np.cumsum(rng.normal(0.002,0.01,n)))
P["close"]["LONER"]=cl; P["open"]["LONER"]=cl; P["high"]["LONER"]=cl*1.005; P["low"]["LONER"]=cl*0.995; P["volume"]["LONER"]=np.full(n,1e6)
P={k:pd.DataFrame(v,index=idx) for k,v in P.items()}
g=pd.Series(groups)
S=ga.ga_state(P,g,top_pct=0.25)
gt=ga.group_table(S)
ok(gt["group"].iloc[0]=="Grp0" and gt["group"].iloc[-1]=="Grp3", f"planted strong group ranks first ({gt['group'].tolist()})")
ok("Solo" not in gt["group"].tolist() and np.isnan(S["group_pct"]["LONER"].iloc[-1]), "group under min size gets no read")
ok(gt["leading"].sum()==1 and bool(gt.loc[0,"leading"]), "top 25% of 4 groups = 1 leading group")
G_=S["G"]; d_=G_["score"].index[-1]; okg=G_["score"].loc[d_].dropna().index
parts=[G_["med_rs"].loc[d_,okg].rank(pct=True),G_["mom"].loc[d_,okg].rank(pct=True),G_["breadth"].loc[d_,okg].rank(pct=True),G_["depth"].loc[d_,okg].rank(pct=True)]
hand=100*(0.4*parts[0]+0.2*parts[1]+0.2*parts[2]+0.2*parts[3])
ok(np.allclose(hand.values,G_["score"].loc[d_,okg].values), "strength = 40/20/20/20 weighted percentiles, by hand")
mr=S["G"]["med_rs"].iloc[-1]; ok(abs(mr["Grp1"]-S["rs"].iloc[-1][[f"G1N{j}" for j in range(10)]].median())<1e-9, "group RS = member median")
ok(abs(S["G"]["breadth"]["Grp0"].iloc[-1]-(P["close"][[f"G0N{j}" for j in range(10)]].iloc[-1]>P["close"][[f"G0N{j}" for j in range(10)]].rolling(50).mean().iloc[-1]).mean())<1e-9, "breadth by hand")
L=S["leader"].iloc[-1]; ok(not L[[f"G3N{j}" for j in range(10)]].any(), "no RS leaders in the planted weak group")
ok(((S["rs"].iloc[-1]>=80)&(S["rs_vs_group"].iloc[-1]>0)).equals(L), "leader = RS>=80 and above group median")

# asymmetry by hand on one crafted name
n2=320; idx2=pd.bdate_range("2024-01-01",periods=n2)
cl=np.r_[np.linspace(50,100,n2-10), np.full(10,100.0)]
hi=cl+1.0; lo=cl-1.0; lo[-3]=97.0  # 5-day low 97
P2={"close":pd.DataFrame({"X":cl},idx2),"open":pd.DataFrame({"X":cl},idx2),"high":pd.DataFrame({"X":hi},idx2),"low":pd.DataFrame({"X":lo},idx2)}
A=ga.asymmetry(P2)
a=ga.atr(P2)["X"].iloc[-1]
levels=[P2["low"]["X"].iloc[-5:].min(),P2["low"]["X"].iloc[-10:].min(),ga.ema(P2["close"],21)["X"].iloc[-1],P2["close"]["X"].iloc[-50:].mean()]
d=[(100-(L_-0.1*a))/a for L_ in levels]; valid=[(x if (x>=0.5 and L_<100) else np.inf) for x,L_ in zip(d,levels)]
kh=int(np.argmin(valid)); risk_hand=valid[kh]
ok(abs(A["risk_atr"]["X"].iloc[-1]-risk_hand)<1e-9 and A["stop_kind"]["X"].iloc[-1]==kh, f"nearest valid support by hand: {ga.GA_STOP_KINDS[kh]} {risk_hand:.2f} ATR (21 EMA at {d[2]:.2f} ATR skipped)")
# tight 5-day low (<0.5 ATR) is skipped
lo2=lo.copy(); lo2[-5:]=99.6; P3=dict(P2); P3["low"]=pd.DataFrame({"X":lo2},idx2)
A3=ga.asymmetry(P3); ok(A3["stop_kind"]["X"].iloc[-1]!=0 or A3["risk_atr"]["X"].iloc[-1]>=0.5, "stop closer than 0.5 ATR skipped")
# reward uses only completed windows: changing the last 20 bars must not change reward at t-20
P4={k:v.copy() for k,v in P2.items()}; P4["high"].iloc[-15:]+=50
r_a=ga.asymmetry(P2)["reward_atr"]["X"].iloc[-21]; r_b=ga.asymmetry(P4)["reward_atr"]["X"].iloc[-21]
ok(abs(r_a-r_b)<1e-12, "reward at t ignores run-ups not complete by t")
# buy-below gives exactly the min R:R
bb,S_,T_=A["buy_below"]["X"].iloc[-1],A["stop"]["X"].iloc[-1],A["target"]["X"].iloc[-1]
rr_at=(T_-bb)/(bb-S_); ok(rr_at>=3-1e-9 and (bb-S_)<=1.5*a+1e-9, f"buy-below meets R:R 3 and the risk cap (R:R {rr_at:.2f})")
ok(A["status"]["X"].iloc[-1] in (0,1,2), "status coded")

# no look-ahead on the full state: state at date t equals state computed on data cut at t
cut=idx[450]; Pc={k:v.loc[:cut] for k,v in P.items()}
S_cut=ga.ga_state(Pc,g,top_pct=0.25)
for k_ in ["rs","group_pct","risk_atr","reward_atr","rr","asym","leader"]:
    a1=S[k_].loc[cut]; a2=S_cut[k_].loc[cut]
    same=((a1==a2)|(a1.isna()&a2.isna())).all() if a1.dtype!=bool else a1.equals(a2)
    ok(bool(same), f"no look-ahead: {k_}")
gt_cut=ga.group_table(S_cut); gt_full=ga.group_table(S,cut)
ok(gt_cut["group"].tolist()==gt_full["group"].tolist(), "group table at t identical with data cut at t")

# event study: hand check one trade
ev=ga.ga_event_study(S,h=10,step=5)
row=ev.iloc[len(ev)//2]; t=row["ticker"]; i=S["rs"].index.get_loc(row["date"])
entry=P["open"][t].iloc[i+1]; stop=S["stop"][t].iloc[i]
lows=P["low"][t].iloc[i+1:i+11].to_numpy(); opens=P["open"][t].iloc[i+1:i+11].to_numpy()
hit=np.where(lows<=stop)[0]
ex=min(opens[hit[0]],stop) if len(hit) else P["close"][t].iloc[i+10]
ok(abs(row["R"]-(ex-entry)/(entry-stop))<1e-9, f"event R by hand ({row['R']:+.2f})")
ok((ev["R"]>=-1-1e-9).sum()>=0.95*len(ev) and (ev.loc[ev.R<-1,"stopped"]).all(), "losses beyond -1R only from gaps through the stop")
ok(ev.groupby("ticker")["date"].apply(lambda s: s.is_monotonic_increasing).all() and set(ev["rr_bucket"])<=set(ga.GA_RR_BUCKETS), "event table shape")
cells=ga.ga_cells(ev,("group","rr_bucket"),10)
lead=ev[ev.lead_group]["R"].mean(); oth=ev[~ev.lead_group]["R"].mean()
ok(lead>oth, f"planted: leading-group trades out-earn the rest ({lead:+.2f} vs {oth:+.2f})")
es=ga.ga_edge_summary(ev,10); ok(set(es)>={"rule_mean_R","diff_t"}, "edge summary")
# placebo: shuffle group labels -> no group edge on average
diffs=[]
for s in range(5):
    gp=pd.Series(np.random.default_rng(s).permutation(g.values),index=g.index)
    Sp=ga.ga_state(P,gp,top_pct=0.25); evp=ga.ga_event_study(Sp,h=10,step=10)
    diffs.append(evp[evp.lead_group]["R"].mean()-evp[~evp.lead_group]["R"].mean())
ok(abs(np.mean(diffs))<abs(lead-oth), f"placebo groups: edge shrinks ({np.mean(diffs):+.2f} vs {lead-oth:+.2f})")

# hooks
nt=ga.name_table(S,only_leading=False)
t0=nt["ticker"].iloc[0]; pts,b=ga.ga_brief_points(t0,nt)
exp=int(nt.iloc[0]["lead_group"])+(1 if nt.iloc[0]["status"]=="Asymmetric now" else -1 if nt.iloc[0]["status"]=="Extended" else 0)
ok(pts==exp and isinstance(b,list), f"brief points {pts} badges {b}")
ok(ga.ga_brief_points("NOPE",nt)==(0,[]), "brief points: unknown ticker")
evs=pd.DataFrame({"date":[idx[400],idx[500],idx[10]],"ticker":["G0N0","G3N1","G0N0"]})
lab=ga.ga_split_labels(evs,S)
ok(lab["ga_group"].iloc[0]==("Leading group" if S["group_pct"].at[idx[400],"G0N0"]>=0.75 else lab["ga_group"].iloc[0]) and lab["ga_group"].iloc[2]=="No group read", f"ledger split labels {lab['ga_group'].tolist()} {lab['ga_rr'].tolist()}")
k=ga.ga_kpis(S); ok(k["groups"]==4 and k["leading_groups"]==1, "kpis")

# demo panel + speed at lab scale
inds=pd.Series({f"T{i}":f"Ind{i%90}" for i in range(1800)})
t1=time.time(); Pd=ga.demo_panel(inds,n=1260); t2=time.time(); Sd=ga.ga_state(Pd,inds); t3=time.time()
gtd=ga.group_table(Sd); ntd=ga.name_table(Sd); t4=time.time(); evd=ga.ga_event_study(Sd,h=20); t5=time.time()
print(f"  1,800 names x 5y: demo {t2-t1:.1f}s, state {t3-t2:.1f}s, tables {t4-t3:.2f}s, replay {t5-t4:.1f}s ({len(evd):,} trades)")
ok(len(gtd)==90 and t3-t2<30, "lab-scale state")
print(R)
