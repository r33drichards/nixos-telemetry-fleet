# Only change after hardware, access and network review. No secret values here.
{ ... }: {
  lab.enable = false;
  lab.hardwareApproved = false;
  lab.networkApproved = false;
  lab.telemetryCapacityApproved = false;
  lab.publicGrafana = false;
  lab.grafanaHostname = "";
  lab.acmeEmail = "";
}
