import {
  Box,
  Divider,
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
} from '@mui/material';
import { Link, useLocation } from 'react-router-dom';
import { menuItems } from './menuItems';

export const SIDEBAR_WIDTH = 248;

export default function Sidebar() {
  const location = useLocation();

  return (
    <Drawer
      variant="permanent"
      sx={{
        width: SIDEBAR_WIDTH,
        flexShrink: 0,
        [`& .MuiDrawer-paper`]: { width: SIDEBAR_WIDTH, boxSizing: 'border-box' },
      }}
    >
      <Toolbar sx={{ px: 3, py: 2.5 }}>
        <Box>
          <Typography
            variant="overline"
            sx={{ color: 'secondary.main', display: 'block', lineHeight: 1.2 }}
          >
            Proactive & Reactive Intelligent Maintenance Assistant
          </Typography>
          <Typography variant="h6" sx={{ lineHeight: 1.2 }}>
            PRIMA
          </Typography>
        </Box>
      </Toolbar>
      <Divider />
      <List sx={{ px: 1.5, py: 1.5 }}>
        {menuItems.map((item) => {
          const isActive = location.pathname.startsWith(item.route);
          return (
            <ListItemButton
              key={item.id}
              component={Link}
              to={item.route}
              selected={isActive}
              sx={{
                borderRadius: 2,
                mb: 0.5,
                '&.Mui-selected': {
                  backgroundColor: 'rgba(255,106,61,0.12)',
                  color: 'primary.main',
                  '& .MuiListItemIcon-root': { color: 'primary.main' },
                },
                '&.Mui-selected:hover': {
                  backgroundColor: 'rgba(255,106,61,0.18)',
                },
              }}
            >
              <ListItemIcon sx={{ minWidth: 36, color: 'text.secondary' }}>
                {item.icon}
              </ListItemIcon>
              <ListItemText
                primary={item.label}
                primaryTypographyProps={{ fontSize: '0.875rem', fontWeight: isActive ? 600 : 500 }}
              />
            </ListItemButton>
          );
        })}
      </List>
      <Box sx={{ mt: 'auto', p: 2 }}>
        <Box
          sx={{
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 2,
            p: 1.5,
            backgroundColor: 'rgba(61,220,151,0.06)',
          }}
        >
          <Typography variant="overline" sx={{ color: 'secondary.main' }}>
            Plant
          </Typography>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            Steel Plant A — Bangalore
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Blast Furnace Unit
          </Typography>
        </Box>
      </Box>
    </Drawer>
  );
}
