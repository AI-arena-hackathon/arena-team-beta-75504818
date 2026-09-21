import React, { useState, useEffect, useCallback, useMemo, memo } from 'react';
import {
  Container,
  AppBar,
  Toolbar,
  Typography,
  Button,
  Card,
  CardContent,
  Grid,
  Chip,
  CircularProgress,
  Alert,
  Snackbar,
  IconButton,
  Tooltip,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Badge,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  ExpandMoreIcon,
} from '@mui/material';
import { VolumeUp, VolumeOff, Refresh, Add, CheckCircle, HelpOutline, WifiOff } from '@mui/icons-material';
import { useVoiceGuidance } from './hooks/useVoice';
import { api, formatPainPoint, getPainPointColor, ApiError } from './utils/api';

const ClusterCard = memo(function ClusterCard({ cluster, onActionClick, announce }) {
  const [expanded, setExpanded] = useState(false);

  const handleExpand = useCallback(() => {
    setExpanded(prev => !prev);
    if (!expanded) {
      announce(`Group ${cluster.id + 1} opened. ${cluster.count} people in this group.`);
    }
  }, [expanded, cluster.id, cluster.count, announce]);

  const needsChips = useMemo(() => {
    if (!cluster.pain_points || cluster.pain_points.length === 0) return null;
    return (
      <div sx={{ mb: 2 }}>
        <Typography variant="h6" sx={{ mb: 1 }}>Support Needs:</Typography>
        <div sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          {cluster.pain_points.map((point, index) => (
            <Chip
              key={point}
              label={formatPainPoint(point)}
              size="small"
              color="default"
              variant="filled"
              sx={{
                backgroundColor: getPainPointColor(point),
                color: point === 'digital_exclusion' ? '#000' : '#fff',
                fontWeight: 500,
              }}
            />
          ))}
        </div>
      </div>
    );
  }, [cluster.pain_points]);

  const seniorsList = useMemo(() => {
    const visibleSeniors = cluster.seniors.slice(0, 10);
    return (
      <List dense>
        {visibleSeniors.map((senior) => (
          <ListItem key={senior.id} divider sx={{ py: 1 }}>
            <ListItemText
              primary={<Typography variant="body1">Person #{senior.id}, Age {senior.age}</Typography>}
              secondary={
                <Typography variant="body2">
                  Mobility: {senior.mobility_flag ? 'Needs Support' : 'Independent'} |{' '}
                  Digital: {senior.digital_engagement ? 'Connected' : 'Limited Access'}
                </Typography>
              }
            />
            <ListItemSecondaryAction>
              <Button
                size="small"
                variant="contained"
                onClick={() => onActionClick(senior)}
                aria-label={`Plan support for person ${senior.id}`}
              >
                <Add fontSize="small" /> Plan Support
              </Button>
            </ListItemSecondaryAction>
          </ListItem>
        ))}
        {cluster.seniors.length > 10 && (
          <ListItem>
            <Typography variant="body2" color="text.secondary">
              ... and {cluster.seniors.length - 10} more people
            </Typography>
          </ListItem>
        )}
      </List>
    );
  }, [cluster.seniors, onActionClick]);

  return (
    <Card sx={{ mb: 3, minHeight: '100%' }}>
      <CardContent>
        <div sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
          <div>
            <Typography variant="h5" component="h2" sx={{ mb: 1 }}>
              Cluster {cluster.id + 1}
            </Typography>
            <Typography variant="body1" color="text.secondary">
              {cluster.count} seniors
            </Typography>
          </div>
          <Chip
            label={cluster.program || 'No Program Assigned'}
            size="small"
            variant="outlined"
            sx={{ fontSize: '0.875rem' }}
          />
        </div>

        {cluster.program_description && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {cluster.program_description}
          </Typography>
        )}

        {needsChips}

        <Accordion expanded={expanded} onChange={handleExpand} sx={{ mt: 2 }}>
          <AccordionSummary
            expandIcon={<ExpandMoreIcon />}
            aria-controls="group-details"
            id="group-summary"
          >
            <Typography variant="body1">View People & Plan Support</Typography>
          </AccordionSummary>
          <AccordionDetails>
            {seniorsList}
          </AccordionDetails>
        </Accordion>
      </CardContent>
    </Card>
  );
});

function ActionModal({ open, senior, onClose, onSubmit, announce }) {
  const [supportType, setSupportType] = useState('exercise');
  const [description, setDescription] = useState('');

  const supportTypes = [
    { value: 'exercise', label: 'Exercise Class' },
    { value: 'health_check', label: 'Health Check-in' },
    { value: 'digital_training', label: 'Digital Skills' },
    { value: 'social', label: 'Social Activity' },
    { value: 'nutrition', label: 'Nutrition Support' },
  ];

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      sx={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        bgcolor: 'rgba(0,0,0,0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1300,
      }}
    >
      <Card sx={{ maxWidth: 500, width: '90%', mx: 2 }}>
        <CardContent>
          <Typography id="modal-title" variant="h5" component="h2" sx={{ mb: 2 }}>
            Plan Support for Person #{senior.id}
          </Typography>
          <Typography variant="body1" sx={{ mb: 2 }}>
            Age: {senior.age} | Mobility: {senior.mobility_flag ? 'Needs Support' : 'Independent'} | Digital: {senior.digital_engagement ? 'Connected' : 'Limited Access'}
          </Typography>

          <div sx={{ mb: 2 }}>
            <Typography variant="body1" sx={{ mb: 1 }}>Type of Support</Typography>
            <div sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {supportTypes.map((type) => (
                <Button
                  key={type.value}
                  variant={supportType === type.value ? 'contained' : 'outlined'}
                  onClick={() => {
                    setSupportType(type.value);
                    announce(`${type.label} selected`);
                  }}
                  fullWidth={false}
                  sx={{ minWidth: 150 }}
                >
                  {type.label}
                </Button>
              ))}
            </div>
          </div>

          <div sx={{ mb: 2 }}>
            <label htmlFor="description" style={{ display: 'block', marginBottom: 8, fontWeight: 500, fontSize: '1.125rem' }}>
              Notes (optional)
            </label>
            <textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              style={{
                width: '100%',
                padding: 12,
                fontSize: '1.125rem',
                borderRadius: 8,
                border: '2px solid #e0e0e0',
                fontFamily: 'inherit',
                resize: 'vertical',
              }}
            />
          </div>

          <div sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
            <Button variant="outlined" size="large" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="contained" size="large" onClick={() => onSubmit(supportType, description)}>
              Add Support Plan
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function SeniorActionsList({ seniorId, onClose, announce, handleApiError }) {
  const [supportPlans, setSupportPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchPlans = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await api.getActions(seniorId);
        setSupportPlans(data || []);
      } catch (err) {
        const message = handleApiError(err, 'Failed to fetch support plans');
        setError(message);
        console.error('Failed to fetch support plans:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchPlans();
  }, [seniorId, handleApiError]);

  const handleComplete = async (planId) => {
    try {
      await api.completeAction(planId);
      announce('Support plan marked as complete');
      setSupportPlans(prev => prev.map(p => p.id === planId ? { ...p, status: 'completed' } : p));
    } catch (err) {
      const message = handleApiError(err, 'Failed to complete support plan');
      announce(message);
    }
  };

  if (error) {
    return (
      <Card sx={{ maxWidth: 600, width: '90%', mx: 2 }}>
        <CardContent>
          <div sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h5" component="h2">Support Plans for Person #{seniorId}</Typography>
            <IconButton onClick={onClose} aria-label="Close">
              <HelpOutline fontSize="large" />
            </IconButton>
          </div>
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
          <Button variant="contained" onClick={() => {
            setError(null);
            setLoading(true);
            api.getActions(seniorId).then(data => {
              setSupportPlans(data);
              setLoading(false);
            }).catch(err => {
              setError(handleApiError(err, 'Failed to fetch support plans'));
              setLoading(false);
            });
          }}>
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card sx={{ maxWidth: 600, width: '90%', mx: 2 }}>
      <CardContent>
        <div sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h5" component="h2">Support Plans for Person #{seniorId}</Typography>
          <IconButton onClick={onClose} aria-label="Close">
            <HelpOutline fontSize="large" />
          </IconButton>
        </div>

        {loading ? (
          <CircularProgress />
        ) : supportPlans.length === 0 ? (
          <Typography variant="body1" color="text.secondary" textAlign="center" sx={{ py: 4 }}>
            No support plans yet
          </Typography>
        ) : (
          <List dense>
            {supportPlans.map((plan) => (
              <ListItem key={plan.id} divider sx={{ py: 1 }}>
                <ListItemText
                  primary={<Typography variant="body1">{plan.action_type.replace('_', ' ')}</Typography>}
                  secondary={
                    <Typography variant="body2">
                      {plan.description} | Status: {plan.status}
                      {plan.completed_at && ` | Completed: ${new Date(plan.completed_at).toLocaleDateString()}`}
                    </Typography>
                  }
                />
                <ListItemSecondaryAction>
                  {plan.status === 'pending' && (
                    <Button
                      size="small"
                      variant="contained"
                      onClick={() => handleComplete(plan.id)}
                      aria-label={`Complete ${plan.action_type}`}
                    >
                      <CheckCircle fontSize="small" /> Done
                    </Button>
                  )}
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>
        )}
      </CardContent>
    </Card>
  );
}

function App() {
  const [clusters, setClusters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'info' });
  const [actionModal, setActionModal] = useState({ open: false, senior: null });
  const [actionsList, setActionsList] = useState({ open: false, seniorId: null });
  const [networkError, setNetworkError] = useState(false);
  const { announce, toggleGuidance, guidanceEnabled, isSpeaking, isSupported, stop } = useVoiceGuidance(true);

  const handleApiError = useCallback((error, defaultMessage) => {
    if (error instanceof ApiError) {
      if (error.status >= 500 && error.status < 600) {
        setNetworkError(true);
        return 'Service temporarily unavailable. Retrying...';
      }
      if (error.status === 408 || error.status === 0) {
        setNetworkError(true);
        return 'Connection timeout. Please check your network.';
      }
      if (error.status === 404) {
        return 'Resource not found';
      }
      if (error.status === 403) {
        return 'Access denied';
      }
      return error.message;
    }
    setNetworkError(true);
    return defaultMessage;
  }, []);

  const showSnackbar = useCallback((message, severity = 'info') => {
    setSnackbar({ open: true, message, severity });
    announce(message);
  }, [announce]);

  const fetchClusters = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getClusters();
      setClusters(data || []);
      setNetworkError(false);
      if (data.length === 0) {
        showSnackbar('No groups yet. Generate groups to see recommendations.', 'warning');
      } else {
        announce(`Loaded ${data.length} groups`);
      }
    } catch (error) {
      setClusters([]);
      const message = handleApiError(error, 'Failed to load groups');
      showSnackbar(message, 'error');
    } finally {
      setLoading(false);
    }
  }, [announce, showSnackbar, handleApiError]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const result = await api.generateClusters();
      if (result.status === 'success') {
        showSnackbar(`Generated ${result.clusters_generated} groups`, 'success');
        fetchClusters();
      } else {
        showSnackbar(result.message || 'Failed to generate groups', 'error');
      }
    } catch (error) {
      const message = handleApiError(error, 'Failed to generate groups');
      showSnackbar(message, 'error');
    } finally {
      setGenerating(false);
    }
  };

  const handleActionClick = (senior) => {
    setActionModal({ open: true, senior });
    announce(`Planning support for person ${senior.id}`);
  };

  const handleActionSubmit = async (supportType, description) => {
    try {
      await api.createAction(actionModal.senior.id, supportType, description);
      showSnackbar('Support plan created successfully', 'success');
      setActionModal({ open: false, senior: null });
    } catch (error) {
      const message = handleApiError(error, 'Failed to create support plan');
      showSnackbar(message, 'error');
    }
  };

  const handleViewPlans = (seniorId) => {
    setActionsList({ open: true, seniorId });
    announce(`Viewing support plans for person ${seniorId}`);
  };

  const handleRefresh = async () => {
    try {
      await api.refreshData();
      showSnackbar('Data refreshed', 'success');
      fetchClusters();
    } catch (error) {
      const message = handleApiError(error, 'Failed to refresh data');
      showSnackbar(message, 'error');
    }
  };

  useEffect(() => {
    fetchClusters();
    announce('Welcome to SeniorCare Pulse. Your dashboard is ready.');
  }, [fetchClusters, announce]);

  useEffect(() => {
    if (guidanceEnabled && clusters.length > 0 && !isSpeaking) {
      const firstCluster = clusters[0];
      announce(`First group has ${firstCluster.count} people. Suggested program: ${firstCluster.program}`);
    }
  }, [clusters, guidanceEnabled, isSpeaking, announce]);

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#F5F5F5' }}>
      <AppBar position="static" elevation={0} sx={{ backgroundColor: '#2E7D32', borderBottom: '3px solid #1B5E20' }}>
        <Toolbar>
          <Typography variant="h4" sx={{ flexGrow: 1, fontWeight: 700, letterSpacing: '-0.5px' }}>
            SeniorCare Pulse
          </Typography>
          <div sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {networkError && (
              <Tooltip title="Connection issue - retrying automatically">
                <Chip
                  icon={<WifiOff fontSize="small" />}
                  label="Offline"
                  size="small"
                  color="error"
                  variant="filled"
                  sx={{ fontWeight: 500 }}
                />
              </Tooltip>
            )}
            {isSupported && (
              <Tooltip title={guidanceEnabled ? 'Turn off voice guidance' : 'Turn on voice guidance'}>
                <IconButton
                  onClick={toggleGuidance}
                  aria-pressed={guidanceEnabled}
                  aria-label={guidanceEnabled ? 'Turn off voice guidance' : 'Turn on voice guidance'}
                  sx={{ backgroundColor: guidanceEnabled ? '#fff' : 'rgba(255,255,255,0.2)', color: guidanceEnabled ? '#2E7D32' : '#fff' }}
                >
                  {guidanceEnabled ? <VolumeUp /> : <VolumeOff />}
                </IconButton>
              </Tooltip>
            )}
            <Tooltip title="Refresh data">
              <IconButton onClick={handleRefresh} aria-label="Refresh data" disabled={loading}>
                <Refresh />
              </IconButton>
            </Tooltip>
            <Tooltip title="Find support groups">
              <Button
                variant="contained"
                color="secondary"
                startIcon={<Add />}
                onClick={handleGenerate}
                disabled={generating}
                size="large"
                aria-label="Find support groups from community data"
              >
                {generating ? <CircularProgress size={20} color="inherit" /> : 'Find Groups'}
              </Button>
            </Tooltip>
          </div>
        </Toolbar>
      </AppBar>

      <Container maxWidth="xl" sx={{ py: 4 }}>
        {loading && clusters.length === 0 && (
          <div sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
            <CircularProgress size={60} />
          </div>
        )}

        {!loading && clusters.length === 0 && (
          <Card sx={{ textAlign: 'center', py: 6, px: 4 }}>
            <CardContent>
              <HelpOutline sx={{ fontSize: 64, color: '#2E7D32', mb: 2 }} />
              <Typography variant="h4" sx={{ mb: 2 }}>No Groups Yet</Typography>
              <Typography variant="body1" color="text.secondary" sx={{ mb: 3, maxWidth: 500, mx: 'auto' }}>
                Click "Find Groups" to analyze the data and discover who needs what kind of support.
              </Typography>
              <Button variant="contained" size="large" onClick={handleGenerate} startIcon={<Add />}>
                Find Groups
              </Button>
            </CardContent>
          </Card>
        )}

        {!loading && clusters.length > 0 && (
          <Grid container spacing={3}>
            {clusters.map((cluster) => (
              <Grid item xs={12} sm={6} lg={4} key={cluster.id}>
                <ClusterCard
                  cluster={cluster}
                  onActionClick={handleActionClick}
                  announce={announce}
                />
              </Grid>
            ))}
          </Grid>
        )}

        <ActionModal
          open={actionModal.open}
          senior={actionModal.senior}
          onClose={() => setActionModal({ open: false, senior: null })}
          onSubmit={handleActionSubmit}
          announce={announce}
        />

        <SeniorActionsList
          open={actionsList.open}
          seniorId={actionsList.seniorId}
          onClose={() => setActionsList({ open: false, seniorId: null })}
          announce={announce}
          handleApiError={handleApiError}
        />
      </Container>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        <Alert onClose={() => setSnackbar({ ...snackbar, open: false })} severity={snackbar.severity} variant="filled">
          {snackbar.message}
        </Alert>
      </Snackbar>
    </div>
  );
}

export default App;