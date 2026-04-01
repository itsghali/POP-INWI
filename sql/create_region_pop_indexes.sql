-- Utility migration to speed up warm-up discovery/loading.
-- Safe to run multiple times (IF NOT EXISTS).

CREATE INDEX IF NOT EXISTS "idx_Etat_CLIM_A_region_pop"
ON "Etat_CLIM_A"("region", "pop");

CREATE INDEX IF NOT EXISTS "idx_Etat_CLIM_B_region_pop"
ON "Etat_CLIM_B"("region", "pop");

CREATE INDEX IF NOT EXISTS "idx_Etat_CLIM_C_region_pop"
ON "Etat_CLIM_C"("region", "pop");

CREATE INDEX IF NOT EXISTS "idx_Etat_CLIM_D_region_pop"
ON "Etat_CLIM_D"("region", "pop");

CREATE INDEX IF NOT EXISTS "idx_Etat_CLIM_E_region_pop"
ON "Etat_CLIM_E"("region", "pop");

CREATE INDEX IF NOT EXISTS "idx_Etat_CLIM_F_region_pop"
ON "Etat_CLIM_F"("region", "pop");

CREATE INDEX IF NOT EXISTS "idx_Etat_CLIM_G_region_pop"
ON "Etat_CLIM_G"("region", "pop");

CREATE INDEX IF NOT EXISTS "idx_Etat_CLIM_H_region_pop"
ON "Etat_CLIM_H"("region", "pop");

CREATE INDEX IF NOT EXISTS "idx_Etat_Porte_region_pop"
ON "Etat_Porte"("region", "pop");

CREATE INDEX IF NOT EXISTS "idx_Temp_Ambiante_region_pop"
ON "Température_Ambiante"("region", "pop");

CREATE INDEX IF NOT EXISTS "idx_Temp_Exterieure_region_pop"
ON "Température_Extérieure"("region", "pop");

CREATE INDEX IF NOT EXISTS "idx_P_Active_CLIM_region_pop"
ON "P.Active_CLIM"("region", "pop");

CREATE INDEX IF NOT EXISTS "idx_P_Active_Generale_region_pop"
ON "P.Active_Générale"("region", "pop");
