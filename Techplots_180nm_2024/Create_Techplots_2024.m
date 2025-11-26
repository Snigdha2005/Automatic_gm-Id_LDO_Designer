close all;
clear all;
clc;

filename1='TechPlot_Sim_Data_180nm_VDS_0p2V.xlsx';
Sim_Data = xlsread(filename1);

nov=Sim_Data(10,:);
ngm=Sim_Data(11,:);
nid=Sim_Data(12,:);
ngm_id=Sim_Data(13,:);
nrout=Sim_Data(14,:);
ngmro=Sim_Data(15,:);
nidw=Sim_Data(16,:);
ncgg=Sim_Data(17,:);
nft=Sim_Data(24,:);
ngm_id_ft=Sim_Data(25,:);


% for count=0:6
% hold on;
% plot(ngm_id(1+count*81:81+count*81),ngmro(1+count*81:81+count*81))
% end

% for count=0:6
% hold on;
% plot(ngm_id(1+count*81:81+count*81),nidw(1+count*81:81+count*81))
% end

% for count=0:6
% hold on;
% plot(ngm_id(1+count*81:81+count*81),nft(1+count*81:81+count*81))
% end

%PMOS CHARACTERIZATION      %%%%%%%%%%%%%%%%%%%%
pov=Sim_Data(30,:);
pgm=Sim_Data(31,:);
pid=Sim_Data(32,:);
pgm_id=Sim_Data(33,:);
prout=Sim_Data(34,:);
pgmro=Sim_Data(35,:);
pidw=Sim_Data(36,:);
pcgg=Sim_Data(37,:);
pft=Sim_Data(44,:);
pgm_id_ft=Sim_Data(45,:);


% for count=0:6
% hold on;
% plot(pgm_id(1+count*81:81+count*81),pgmro(1+count*81:81+count*81))
% end

% for count=0:6
% hold on;
% plot(pgm_id(1+count*81:81+count*81),pidw(1+count*81:81+count*81))
% end

% for count=0:6
% hold on;
% plot(pgm_id(1+count*81:81+count*81),pft(1+count*81:81+count*81))
% end
