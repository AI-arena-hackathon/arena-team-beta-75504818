import React, { useState, useEffect, useCallback } from 'react';
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
import { VolumeUp, VolumeOff, Refresh, Add, CheckCircle, HelpOutline } from '@mui/icons-material';
import { useVoiceGuidance } from './hooks/useVoice';
import { api, formatPainPoint, getPainPointColor } from './utils/api';

function ClusterCard({ cluster, onActionClick, announce }) {
  const [expanded, setExpanded] = useState(false);

  const handleExpand = () => {
    setExpanded(!expanded);
    if (!expanded) {
      announce(`Cluster ${cluster.id + 1} expanded. ${cluster.count} seniors.`);
    }
  };

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

        {cluster.pain_points && cluster.pain_points.length > 0 && (
          <div sx={{ mb: 2 }}>
            <Typography variant="h6" sx={{ mb: 1 }}>Pain Points:</Typography>
            <div sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {cluster.pain_points.map((point, index) => (
                <Chip
                  key={index}
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
        )}

        <Accordion expanded={expanded} onChange={handleExpand} sx={{ mt: 2 }}>
          <AccordionSummary
            expandIcon={<ExpandMoreIcon />}
            aria-controls="cluster-details"
            id="cluster-summary"
          >
            <Typography variant="body1">View Seniors & Actions</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <List dense>
              {cluster.seniors.slice(0, 10).map((senior) => (
                <ListItem key={senior.id} divider sx={{ py: 1 }}>
                  <ListItemText
                    primary={<Typography variant="body1">Senior #{senior.id} - Age {senior.age}</Typography>}
                    secondary={
                      <Typography variant="body2">
                        Mobility: {senior.mobility_flag ? 'Needs Support' : 'Independent'} |{' '}
                        Digital: {senior.digital_engagement ? 'Engaged' : 'Not Engaged'}
                      </Typography>
                    }
                  />
                  <ListItemSecondaryAction>
                    <Button
                      size="small"
                      variant="contained"
                      onClick={() => onActionClick(senior)}
                      aria-label={`Create action for senior ${senior.id}`}
                    >
                      <Add fontSize="small" /> Action
                    </Button>
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
              {cluster.seniors.length > 10 && (
                <ListItem>
                  <Typography variant="body2" color="text.secondary">
                    ... and {cluster.seniors.length - 10} more seniors
                  </Typography>
                </ListItem>
              )}
            </List>
          </AccordionDetails>
        </Accordion>
      </CardContent>
    </Card>
  );
}

function ActionModal({ open, senior, onClose, onSubmit, announce }) {
  const [actionType, setActionType] = useState('exercise');
  const [description, setDescription] = useState('');

  const actionTypes = [
    { value: 'exercise', label: 'Exercise Class' },
    { value: 'health_check', label: 'Health Check-in' },
    { value: 'digital_training', label: 'Digital Training' },
    { value: 'social', label: 'Social Activity' },
    { value: 'nutrition', label: 'Nutrition Counseling' },
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
            Create Action for Senior #{senior.id}
          </Typography>
          <Typography variant="body1" sx={{ mb: 2 }}>
            Age: {senior.age} | Mobility: {senior.mobility_flag ? 'Needs Support' : 'Independent'} | Digital: {senior.digital_engagement ? 'Engaged' : 'Not Engaged'}
          </Typography>

          <div sx={{ mb: 2 }}>
            <Typography variant="body1" sx={{ mb: 1 }}>Action Type</Typography>
            <div sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {actionTypes.map((type) => (
                <Button
                  key={type.value}
                  variant={actionType === type.value ? 'contained' : 'outlined'}
                  onClick={() => {
                    setActionType(type.value);
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
              Description (optional)
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
            <Button variant="contained" size="large" onClick={() => onSubmit(actionType, description)}>
              Create Action
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function SeniorActionsList({ seniorId, onClose, announce }) {
  const [actions, setActions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchActions = async () => {
      try {
        const data = await api.getActions(seniorId);
        setActions(data);
      } catch (error) {
        console.error('Failed to fetch actions:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchActions();
  }, [seniorId]);

  const handleComplete = async (actionId) => {
    try {
      await api.completeAction(actionId);
      announce('Action marked as complete');
      setActions(prev => prev.map(a => a.id === actionId ? { ...a, status: 'completed' } : a));
    } catch (error) {
      announce('Failed to complete action');
    }
  };

  return (
    <Card sx={{ maxWidth: 600, width: '90%', mx: 2 }}>
      <CardContent>
        <div sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h5" component="h2">Actions for Senior #{seniorId}</Typography>
          <IconButton onClick={onClose} aria-label="Close">
            <HelpOutline fontSize="large" />
          </IconButton>
        </div>

        {loading ? (
          <CircularProgress />
        ) : actions.length === 0 ? (
          <Typography variant="body1" color="text.secondary" textAlign="center" sx={{ py: 4 }}>
            No actions yet
          </Typography>
        ) : (
          <List dense>
            {actions.map((action) => (
              <ListItem key={action.id} divider sx={{ py: 1 }}>
                <ListItemText
                  primary={<Typography variant="body1">{action.action_type.replace('_', ' ')}</Typography>}
                  secondary={
                    <Typography variant="body2">
                      {action.description} | Status: {action.status}
                      {action.completed_at && ` | Completed: ${new Date(action.completed_at).toLocaleDateString()}`}
                    </Typography>
                  }
                />
                <ListItemSecondaryAction>
                  {action.status === 'pending' && (
                    <Button
                      size="small"
                      variant="contained"
                      onClick={() => handleComplete(action.id)}
                      aria-label={`Complete action ${action.action_type}`}
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
  const { announce, toggleGuidance, guidanceEnabled, isSpeaking, isSupported, stop } = useVoiceGuidance(true);

  const showSnackbar = useCallback((message, severity = 'info') => {
    setSnackbar({ open: true, message, severity });
    announce(message);
  }, [announce]);

  const fetchClusters = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getClusters();
      setClusters(data);
      if (data.length === 0) {
        showSnackbar('No clusters yet. Generate clusters to see recommendations.', 'warning');
      } else {
        announce(`Loaded ${data.length} clusters`);
      }
    } catch (error) {
      showSnackbar('Failed to load clusters', 'error');
    } finally {
      setLoading(false);
    }
  }, [announce, showSnackbar]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const result = await api.generateClusters();
      if (result.status === 'success') {
        showSnackbar(`Generated ${result.clusters_generated} clusters`, 'success');
        fetchClusters();
      } else {
        showSnackbar(result.message || 'Failed to generate clusters', 'error');
      }
    } catch (error) {
      showSnackbar('Failed to generate clusters', 'error');
    } finally {
      setGenerating(false);
    }
  };

  const handleActionClick = (senior) => {
    setActionModal({ open: true, senior });
    announce(`Creating action for senior ${senior.id}`);
  };

  const handleActionSubmit = async (actionType, description) => {
    try {
      await api.createAction(actionModal.senior.id, actionType, description);
      showSnackbar('Action created successfully', 'success');
      setActionModal({ open: false, senior: null });
    } catch (error) {
      showSnackbar('Failed to create action', 'error');
    }
  };

  const handleViewActions = (seniorId) => {
    setActionsList({ open: true, seniorId });
    announce(`Viewing actions for senior ${seniorId}`);
  };

  const handleRefresh = async () => {
    try {
      await api.refreshData();
      showSnackbar('Data refreshed', 'success');
      fetchClusters();
    } catch (error) {
      showSnackbar('Failed to refresh data', 'error');
    }
  };

  useEffect(() => {
    fetchClusters();
    announce('Welcome to SeniorCare Pulse. Dashboard loaded.');
  }, [fetchClusters, announce]);

  useEffect(() => {
    if (guidanceEnabled && clusters.length > 0 && !isSpeaking) {
      const firstCluster = clusters[0];
      announce(`First cluster has ${firstCluster.count} seniors. Recommended program: ${firstCluster.program}`);
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
            {isSupported && (
              <Tooltip title={guidanceEnabled ? 'Disable voice guidance' : 'Enable voice guidance'}>
                <IconButton
                  onClick={toggleGuidance}
                  aria-pressed={guidanceEnabled}
                  aria-label={guidanceEnabled ? 'Disable voice guidance' : 'Enable voice guidance'}
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
            <Tooltip title="Generate clusters">
              <Button
                variant="contained"
                color="secondary"
                startIcon={<Add />}
                onClick={handleGenerate}
                disabled={generating}
                size="large"
                aria-label="Generate clusters from senior data"
              >
                {generating ? <CircularProgress size={20} color="inherit" /> : 'Generate Clusters'}
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
              <Typography variant="h4" sx={{ mb: 2 }}>No Clusters Generated</Typography>
              <Typography variant="body1" color="text.secondary" sx={{ mb: 3, maxWidth: 500, mx: 'auto' }}>
                Click "Generate Clusters" to analyze senior data and create targeted program recommendations.
              </Typography>
              <Button variant="contained" size="large" onClick={handleGenerate} startIcon={<Add />}>
                Generate Clusters
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