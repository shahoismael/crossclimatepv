function baseDir = crossclimatepv_config()
%CROSSCLIMATEPV_CONFIG Resolve the CrossClimatePV data directory.
%
%   baseDir = CROSSCLIMATEPV_CONFIG() returns the directory that holds the four
%   source archives and receives all generated output. Every script in this
%   repository calls this instead of hardcoding a path, so the pipeline runs
%   unmodified on any machine.
%
%   Resolution order:
%
%     1. The CROSSCLIMATEPV_DATA environment variable, if set. Use this when the
%        archives live outside the repository, which is usual — they are
%        roughly 20 GB and are not redistributed here.
%
%          Windows (PowerShell):  $env:CROSSCLIMATEPV_DATA = "D:\pv_data"
%          Windows (cmd):         set CROSSCLIMATEPV_DATA=D:\pv_data
%          Linux / macOS:         export CROSSCLIMATEPV_DATA=/mnt/pv_data
%          Or from inside MATLAB: setenv('CROSSCLIMATEPV_DATA', 'D:\pv_data')
%
%     2. The data/ directory of this repository, if it contains the archives.
%
%   Expected layout, whichever location is used:
%
%       <baseDir>/
%           1_DKASC_AliceSprings_AU/
%           2_HKUST_Rooftop_HK/
%           3_Ausgrid_Sydney_AU/
%           4_PVDAQ_NREL_US/
%
%   The archives themselves must be obtained from their original providers;
%   see LICENSE-DATA. Generated output (harmonized/, protocol/, results/,
%   leaderboard/) is created under baseDir as the pipeline runs.
%
%   See also RUN_HARMONIZATION, PHASE2_PROTOCOL_DESIGN.

SOURCE_DIRS = { ...
    '1_DKASC_AliceSprings_AU', ...
    '2_HKUST_Rooftop_HK', ...
    '3_Ausgrid_Sydney_AU', ...
    '4_PVDAQ_NREL_US'};

repoDir  = fileparts(mfilename('fullpath'));
envDir   = getenv('CROSSCLIMATEPV_DATA');
if isempty(envDir)                       % legacy name, pre-v1.1 releases
    envDir = getenv('SOLARBENCH_DATA');
end
localDir = fullfile(repoDir, 'data');

if ~isempty(envDir)
    baseDir = envDir;
    if ~exist(baseDir, 'dir')
        error('crossclimatepv:missingDataDir', ...
            ['CROSSCLIMATEPV_DATA is set to "%s", which does not exist.\n' ...
             'Point it at the directory holding the four source archives, ' ...
             'or unset it to fall back to %s.'], baseDir, localDir);
    end
else
    baseDir = localDir;
end

present = cellfun(@(d) exist(fullfile(baseDir, d), 'dir') == 7, SOURCE_DIRS);

if ~any(present)
    error('crossclimatepv:noSourceData', ...
        ['No source archives found in "%s".\n\n' ...
         'CrossClimatePV does not redistribute the four source datasets. Obtain ' ...
         'each one from its original provider (see LICENSE-DATA), then place ' ...
         'them as:\n\n' ...
         '    %s\n' ...
         '        1_DKASC_AliceSprings_AU/\n' ...
         '        2_HKUST_Rooftop_HK/\n' ...
         '        3_Ausgrid_Sydney_AU/\n' ...
         '        4_PVDAQ_NREL_US/\n\n' ...
         'If they live elsewhere, set CROSSCLIMATEPV_DATA to that directory:\n' ...
         '    setenv(''CROSSCLIMATEPV_DATA'', ''D:\\your\\path'')'], ...
         baseDir, baseDir);
end

if ~all(present)
    warning('crossclimatepv:partialSourceData', ...
        'Missing source archive(s) in "%s": %s. Steps needing them will fail.', ...
        baseDir, strjoin(SOURCE_DIRS(~present), ', '));
end

end
