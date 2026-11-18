import math, numpy as np, pandas as pd
import group_asym as ga
R={"pass":0,"fail":0}
def ok(c,msg): R["pass" if c else "fail"]+=1; print(("PASS " if c else "FAIL ")+msg)
rng=np.random.default_rng(1)
# 1-2 gambler's ruin (p fixed via a huge beta prior, unit steps)
for p,U,L in [(0.5,4,2),(0.6,5,3),(0.4,3,3)]:
    hu,hd,mk=ga.burst_walk(np.array([p]),1,1,U,L,2000)
    q=1-p; exact=L/(U+L) if p==0.5 else (1-(q/p)**L)/(1-(q/p)**(U+L))
    ok(abs(hu.sum()-exact)<1e-9 and abs(hu.sum()+hd.sum()-1)<1e-9, f"gambler's ruin p={p} U={U} L={L}: {hu.sum():.6f} vs {exact:.6f}")
# fair game: E[R] -> 0 at long horizons
prm={"alpha":2000.0,"beta":10000.0,"ap":5e5,"bp":5e5,"s_up":1.0,"s_dn":1.0,"sig":1.0}
o=ga.burst_odds(prm,1.0,2.0,[2000],grid=0.25)
ok(abs(o["p_target"][0]-1/3)<0.01 and abs(o["e_r"][0])<0.02, f"fair walk: P(target)={o['p_target'][0]:.3f} ~ 1/3, E[R]={o['e_r'][0]:+.3f} ~ 0")
# 3 NB moments
pm=ga.nb_pmf_matrix(3.5,40.0,[20,60],400); k=np.arange(401)
for r_,t in zip(pm,[20,60]):
    m=(r_*k).sum(); v=(r_*k*k).sum()-m*m; m0=3.5/40*t
    ok(abs(r_.sum()-1)<1e-9 and abs(m-m0)<1e-6 and abs(v-m0*(1+t/40))<1e-5, f"NB predictive t={t}: mean {m:.3f}, var {v:.3f}")
# 4 Monte Carlo of the full model
prm={"alpha":12.0,"beta":80.0,"ap":14.0,"bp":10.0,"s_up":1.6,"s_dn":1.3,"sig":1.0}
risk,rew,h=1.25,3.5,20
o=ga.burst_odds(prm,risk,rew,[h])
n=200000; lam=rng.gamma(prm["alpha"],1/prm["beta"],n); N=rng.poisson(lam*h); p=rng.beta(prm["ap"],prm["bp"],n)
g=0.25; U=math.ceil(rew/g); L=math.ceil(risk/g); us=round(prm["s_up"]/g); ds=round(prm["s_dn"]/g)
hitT=np.zeros(n,bool); hitS=np.zeros(n,bool); x=np.zeros(n); alive=np.ones(n,bool)
for step in range(N.max()):
    m=alive&(N>step)
    if not m.any(): break
    u=rng.random(n)<p
    x=np.where(m, x+np.where(u,us,-ds), x)
    t_=m&(x>=U); s_=m&(x<=-L); hitT|=t_; hitS|=s_; alive&=~(t_|s_)
se=math.sqrt(o["p_target"][0]*(1-o["p_target"][0])/n)
ok(abs(hitT.mean()-o["p_target"][0])<4*se, f"Monte Carlo agrees: target {hitT.mean():.4f} vs {o['p_target'][0]:.4f}")
ok(abs(hitS.mean()-o["p_stop"][0])<4*math.sqrt(o["p_stop"][0]*(1-o['p_stop'][0])/n), f"Monte Carlo agrees: stop {hitS.mean():.4f} vs {o['p_stop'][0]:.4f}")
mc_er=np.where(hitT,U*g/risk,np.where(hitS,-1,x*g/risk)).mean()
# model's target R is reward/risk (not the grid overshoot); compare with that convention
mc_er2=np.where(hitT,rew/risk,np.where(hitS,-1,x*g/risk)).mean()
ok(abs(mc_er2-o["e_r"][0])<0.02, f"E[R] agrees: {mc_er2:+.3f} vs {o['e_r'][0]:+.3f}")
# timing curve monotone, timing sensible
oc=ga.burst_odds(prm,risk,rew,np.arange(1,121)); tm=ga.burst_timing(oc)
ok(np.all(np.diff(oc["p_target"])>=-1e-12) and tm["q25"]<=tm["median"]<=tm["q75"], f"timing: median {tm['median']:.0f} sessions (25-75%: {tm['q25']:.0f}-{tm['q75']:.0f})")
# 5 Gaussian walk vs Monte Carlo on continuous scale
sig=0.9; pu,pd_=ga.gauss_odds(sig,1.5,3.0,20,grid=0.05)
z=rng.normal(0,sig,(100000,20)).cumsum(1); hu_=(z>=3.0); hd_=(z<=-1.5)
fu=np.where(hu_.any(1),hu_.argmax(1),99); fd=np.where(hd_.any(1),hd_.argmax(1),99)
mcu=((fu<99)&(fu<fd)).mean(); mcd=((fd<99)&(fd<fu)).mean()
ok(abs(pu-mcu)<0.01 and abs(pd_-mcd)<0.01, f"Gaussian two-barrier vs Monte Carlo: {pu:.3f}/{pd_:.3f} vs {mcu:.3f}/{mcd:.3f}")
# 6 barrier outcome by hand
idx=pd.bdate_range("2024-01-01",periods=8)
H=pd.DataFrame({"A":[10,10.5,11,12.2,11,11,11,11],"B":[10,10.2,10.4,10.6,10.8,11,11,11],"C":[10,11,12.5,11,11,11,11,11]},idx,dtype=float)
Lw=pd.DataFrame({"A":[9.5,10,10.5,11,10,10,10,10],"B":[9.5,9.8,9.9,9.95,10,10,10,10],"C":[9.5,10,8.9,10,10,10,10,10]},idx,dtype=float)
t_,s_=ga.barrier_outcome({"high":H,"low":Lw},0,np.array([0,1,2]),np.array([9.0,9.0,9.0]),np.array([12.0,12.0,12.0]),5)
ok(list(t_)==[True,False,False] and list(s_)==[False,False,True], "barrier outcome: target first / neither / same-day counts as stop")
# 7 no look-ahead and shrinkage
groups=pd.Series({f"T{i}":f"G{i%5}" for i in range(60)})
P=ga.demo_panel(groups,n=500,seed=3)
a=ga.atr(P); B=ga.burst_state(P,a,groups)
cut=P["close"].index[400]; Pc={k:v.loc[:cut] for k,v in P.items()}; Bc=ga.burst_state(Pc,ga.atr(Pc),groups)
same=all(((B[k].loc[cut]==Bc[k].loc[cut])|(B[k].loc[cut].isna()&Bc[k].loc[cut].isna())).all() for k in ["nu","nd","su","sd","g_rate","g_pup","sig"])
ok(same, "burst panels at t identical with data cut at t")
i=len(P["close"])-1; j=0; prm=ga.burst_params(B,i,j)
raw=(B["nu"].iat[i,j]+B["nd"].iat[i,j])/B["nobs"].iat[i,j]; grp=B["g_rate"].iat[i,j]
ok(min(raw,grp)-1e-12<=prm["rate"]<=max(raw,grp)+1e-12, f"gamma posterior rate {prm['rate']:.4f} sits between own {raw:.4f} and group {grp:.4f}")
d=B["d"]; ok(abs(B["nu"].iat[i,j]-((d.iloc[i-125:i+1,j]>=1.0).sum()))<1e-9, "up-burst count by hand (126 sessions)")
# 8 calibration on demo runs, probabilities in [0,1], outcomes binary
S=ga.ga_state(P,groups,top_pct=0.2); Bs=ga.burst_state(P,S["atr"],groups)
cal=ga.ga_burst_calibration(S,Bs,h=20,max_n=800)
ok(len(cal)>100 and cal[["p_burst","p_gauss"]].stack().between(0,1).all() and set(cal["y"].unique())<= {0,1}, f"calibration rows {len(cal)}")
sc=ga.calibration_scores(cal); print(sc.round(4).to_string(index=False))
rel=ga.reliability(cal,"p_burst"); ok(len(rel)==10, "reliability table")
tb=ga.ga_burst_table(S,Bs,list(S["rs"].columns[:10])); ok({"p_target","burst_er","days_median"}<=set(tb.columns), "burst table")
print(R)
