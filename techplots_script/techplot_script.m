close all;
clear;
clc;

filename1 = 'TechPlot_Sim_Data_180nm_VDS_0p4V.xlsx';
Sim_Data = xlsread(filename1);

% -----------------------------
% Extract rows
% -----------------------------
ngm_id = Sim_Data(13,:);
ngmro  = Sim_Data(15,:);
nidw   = Sim_Data(16,:);
nft    = Sim_Data(24,:);

% -----------------------------
% Parameters
% -----------------------------
num_curves = 7;
points_per_curve = 81;

line_styles = {'-', '--', ':', '-.', '-', '--',':'};
markers     = {'none','none','none','none','o','o','o'};   % round markers only for last 2
% Channel lengths for legend (nm)
L_nm = 180:180:1260;

legend_labels = arrayfun(@(L) sprintf('%d nm', L), ...
                          L_nm, 'UniformOutput', false);

% -----------------------------
% Helper function for x-ticks
% -----------------------------
set_xticks = @(x) set(gca, 'XTick', ...
    floor(min(x)/2)*2 : 2 : ceil(max(x)/2)*2);

% -----------------------------
% 1️⃣ gm·ro vs gm/Id
% -----------------------------
figure;
hold on; grid on; box on;

for count = 0:num_curves-1
    idx = 1 + count*points_per_curve : ...
          (count+1)*points_per_curve;

    plot(ngm_id(idx), ngmro(idx), ...
        'LineStyle', line_styles{count+1}, ...
        'Marker', markers{count+1}, ...
    'MarkerSize', 3, ...
        'LineWidth', 1.5);
end

x_min = min(ngm_id(:));
x_max = max(ngm_id(:));

xlim([x_min x_max]);
xticks(x_min:2:x_max);
xlabel('g_m / I_D (V^{-1})');
ylabel('g_m r_o');
title('g_m r_o vs g_m / I_D');
legend(legend_labels, 'Location', 'best');

set_xticks(ngm_id);
set(gca,'FontSize',11);

% -----------------------------
% 2️⃣ Id/W vs gm/Id
% -----------------------------
figure;
hold on; grid on; box on;

for count = 0:num_curves-1
    idx = 1 + count*points_per_curve : ...
          (count+1)*points_per_curve;

    plot(ngm_id(idx), nidw(idx), ...
        'LineStyle', line_styles{count+1}, ...
        'Marker', markers{count+1}, ...
    'MarkerSize', 3, ...
        'LineWidth', 1.5);
end
x_min = min(ngm_id(:));
x_max = max(ngm_id(:));

xlim([x_min x_max]);
xticks(x_min:2:x_max);
xlabel('g_m / I_D (V^{-1})');
ylabel('I_D / W (A/m)');
title('I_D / W vs g_m / I_D');
legend(legend_labels, 'Location', 'best');

set_xticks(ngm_id);
set(gca,'FontSize',11);

% -----------------------------
% 3️⃣ fT vs gm/Id
% -----------------------------
figure;
hold on; grid on; box on;

for count = 0:num_curves-1
    idx = 1 + count*points_per_curve : ...
          (count+1)*points_per_curve;

    plot(ngm_id(idx), nft(idx), ...
        'LineStyle', line_styles{count+1}, ...
        'Marker', markers{count+1}, ...
    'MarkerSize', 3, ...
        'LineWidth', 1.5);
end
x_min = min(ngm_id(:));
x_max = max(ngm_id(:));

xlim([x_min x_max]);
xticks(x_min:2:x_max);
xlabel('g_m / I_D (V^{-1})');
ylabel('f_T (Hz)');
title('f_T vs g_m / I_D');
legend(legend_labels, 'Location', 'best');

set_xticks(ngm_id);
set(gca,'FontSize',11);