import { Box, Card, CardContent, Typography } from '@mui/material';
import FactoryOutlinedIcon from '@mui/icons-material/FactoryOutlined';
import { usePlants } from '@/hooks/usePlants';
import LoadingState from '@/components/common/LoadingState';
import ErrorState from '@/components/common/ErrorState';
import EmptyState from '@/components/common/EmptyState';

export default function PlantPage() {
  const { data, isLoading, isError, error, refetch } = usePlants();

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box>
        <Typography variant="h4" gutterBottom>
          Plants
        </Typography>
        <Typography variant="body2" color="text.secondary">
          All plants monitored by the maintenance wizard.
        </Typography>
      </Box>

      {isLoading && <LoadingState label="Loading plants…" />}
      {isError && <ErrorState message={error?.message} onRetry={() => refetch()} />}

      {data && data.length === 0 && (
        <EmptyState
          icon={<FactoryOutlinedIcon sx={{ fontSize: 32, opacity: 0.4 }} />}
          title="No plants configured"
          description="Plant records will appear once seeded via the startup data files."
        />
      )}

      {data && data.length > 0 && (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', md: 'repeat(3, 1fr)' },
            gap: 2,
          }}
        >
          {data.map((plant) => (
            <Card key={plant.id} variant="outlined">
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
                  <Box
                    sx={{
                      width: 40,
                      height: 40,
                      borderRadius: 2,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      backgroundColor: 'rgba(255,106,61,0.12)',
                      color: 'primary.main',
                    }}
                  >
                    <FactoryOutlinedIcon />
                  </Box>
                  <Box>
                    <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                      {plant.name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {plant.location}
                    </Typography>
                  </Box>
                </Box>
                {plant.description && (
                  <Typography variant="body2" color="text.secondary">
                    {plant.description}
                  </Typography>
                )}
              </CardContent>
            </Card>
          ))}
        </Box>
      )}
    </Box>
  );
}
