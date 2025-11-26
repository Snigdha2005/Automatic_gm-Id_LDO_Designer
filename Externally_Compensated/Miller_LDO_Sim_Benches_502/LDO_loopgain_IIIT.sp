* C:\Users\SnigdhaYS\Documents\LTSpice_LDO_Automation\Externally_Compensated\Miller_LDO_Sim_Benches_502\LDO_loopgain_IIIT.asc
m1 otaout vref n003 n003 nmos292p l=7.2e-007 w=4e-006
m2 n001 n002 n003 n003 nmos292p l=7.2e-007 w=4e-006
m3 n003 bias 0 0 nmos292p l=1u w=10u
m4 n001 n001 vdd vdd pmos292p l=1.8e-007 w=3e-006
m5 otaout n001 vdd vdd pmos292p l=1.8e-007 w=3e-006
mpass out otaout vdd vdd pmos292p l=0.18u w=0.00133
m7 out bias 0 0 nmos292p l=1u w=10u
v1 vdd 0 1.4 ac 0
v2 vref 0 1
m8 bias bias 0 0 nmos292p l=1u w=10u
i1 vdd bias 5e-005
iload out 0 0.002
c2 out 0 2e-009
v3 n002 n004 0 ac 1
r1 out n004 1g
c3 n004 0 1
.ac dec 20 10 1g
.model pmos292p pmos (level=49 version=3.1 tnom=27 tox=4.1e-9 xj=1e-7 nch=4.1589e17 vth0=-0.3823437 k1=0.5722049 k2=0.0219717 k3=0.1576753 k3b=4.2763642 w0=1e-6 nlx=1.104212e-7 dvt0w=0 dvt1w=0 dvt2w=0 dvt0=0.6234839 dvt1=0.2479255 dvt2=0.1 u0=109.4682454 ua=1.31646e-9 ub=1e-21 uc=-1e-10 vsat=1.054892e5 a0=1.5796859 ags=0.3115024 b0=4.729297e-7 b1=1.446715e-6 keta=0.0298609 a1=0.3886886 a2=0.4010376 rdsw=199.1594405 prwg=0.5 prwb=-0.4947034 wr=1 wint=0 lint=2.93948e-8 xl=0 xw=-1e-8 dwg=-1.998034e-8 dwb=-2.481453e-9 voff=-0.0935653 nfactor=2 cit=0 cdsc=2.4e-4 cdscd=0 cdscb=0 eta0=3.515392e-4 etab=-4.804338e-4 dsub=1.215087e-5 pclm=0.96422 pdiblc1=3.026627e-3 pdiblc2=-1e-5 pdiblcb=-1e-3 drout=1.117016e-4 pscbe1=7.999986e10 pscbe2=8.271897e-10 pvag=0.0190118 delta=0.01 rsh=8.1 mobmod=1 prt=0 ute=-1.5 kt1=-0.11 kt1l=0 kt2=0.022 ua1=4.31e-9 ub1=-7.61e-18 uc1=-5.6e-11 at=3.3e4 wl=0 wln=1 ww=0 wwn=1 wwl=0 ll=0 lln=1 lw=0 lwn=1 lwl=0 capmod=2 xpart=0.5 cgdo=7.82e-10 cgso=7.82e-10 cgbo=1e-12 cj=1.214428e-3 pb=0.8461606 mj=0.4192076 cjsw=2.165642e-10 pbsw=0.8 mjsw=0.3202874 cjswg=4.22e-10 pbswg=0.8 mjswg=0.3202874 cf=0 pvth0=5.167913e-4 prdsw=9.5068821 pk2=1.095907e-3 wketa=0.0133232 lketa=-3.648003e-3 pu0=-1.0674346 pua=-4.30826e-11 pub=1e-21 pvsat=50 peta0=1e-4 pketa=-1.822724e-3)
.model nmos292p nmos (level=49 version=3.1 tnom=27 tox=4.1e-9 xj=1e-7 nch=2.3549e17 vth0=0.3694303 k1=0.5789116 k2=1.110723e-3 k3=1e-3 k3b=0.0297124 w0=1e-7 nlx=2.037748e-7 dvt0w=0 dvt1w=0 dvt2w=0 dvt0=1.2953626 dvt1=0.3421545 dvt2=0.0395588 u0=293.1687573 ua=-1.21942e-9 ub=2.325738e-18 uc=7.061289e-11 vsat=1.676164e5 a0=2 ags=0.4764546 b0=1.617101e-7 b1=5e-6 keta=-0.0138552 a1=1.09168e-3 a2=0.3303025 rdsw=105.6133217 prwg=0.5 prwb=-0.2 wr=1 wint=2.885735e-9 lint=1.715622e-8 xl=0 xw=-1e-8 dwg=2.754317e-9 dwb=-3.690793e-9 voff=-0.0948017 nfactor=2.1860065 cit=0 cdsc=2.4e-4 cdscd=0 cdscb=0 eta0=2.665034e-3 etab=6.028975e-5 dsub=0.0442223 pclm=1.746064 pdiblc1=0.3258185 pdiblc2=2.701992e-3 pdiblcb=-0.1 drout=0.9787232 pscbe1=4.494778e10 pscbe2=3.672074e-8 pvag=0.0122755 delta=0.01 rsh=7 mobmod=1 prt=0 ute=-1.5 kt1=-0.11 kt1l=0 kt2=0.022 ua1=4.31e-9 ub1=-7.61e-18 uc1=-5.6e-11 at=3.3e4 wl=0 wln=1 ww=0 wwn=1 wwl=0 ll=0 lln=1 lw=0 lwn=1 lwl=0 capmod=2 xpart=0.5 cgdo=8.58e-10 cgso=8.58e-10 cgbo=1e-12 cj=9.471097e-4 pb=0.8 mj=0.3726161 cjsw=1.905901e-10 pbsw=0.8 mjsw=0.1369758 cjswg=3.3e-10 pbswg=0.8 mjswg=0.1369758 cf=0 pvth0=-5.105777e-3 prdsw=-1.1011726 pk2=2.247806e-3 wketa=-5.071892e-3 lketa=5.324922e-4 pu0=-4.0206081 pua=-4.48232e-11 pub=5.018589e-24 pvsat=2e3 peta0=1e-4 pketa=-2.090695e-3)
*op
.end
