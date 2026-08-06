import { withSupabase } from "npm:@supabase/server@1.4.1";
import type { Database } from "../_shared/database.types.ts";

const roles = new Set(["member", "analyst", "admin"]);
const membershipStatuses = new Set(["pending", "active", "suspended"]);
const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type UserAction = {
  action?: "create" | "update" | "delete";
  user_id?: string;
  email?: string;
  password?: string;
  full_name?: string;
  organization?: string;
  province?: string;
  role?: string;
  membership_status?: string;
};

function json(body: Record<string, unknown>, status = 200): Response {
  return Response.json(body, { status });
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : "Unexpected server error";
}

export default {
  fetch: withSupabase<Database>({ auth: "user" }, async (request, context) => {
    if (request.method !== "POST") {
      return json({ error: "Method not allowed" }, 405);
    }

    const callerId = context.userClaims?.id;
    if (!callerId) {
      return json({ error: "Your session is invalid or expired" }, 401);
    }
    const adminClient = context.supabaseAdmin;
    const { data: callerProfile, error: callerProfileError } = await adminClient
      .from("profiles")
      .select("id, role, membership_status")
      .eq("id", callerId)
      .single();
    if (
      callerProfileError ||
      !callerProfile ||
      callerProfile.role !== "admin" ||
      callerProfile.membership_status !== "active"
    ) {
      return json({ error: "Active administrator access required" }, 403);
    }

    let payload: UserAction;
    try {
      payload = await request.json();
    } catch {
      return json({ error: "A valid JSON request is required" }, 400);
    }

    if (
      payload.action !== "create" &&
      payload.action !== "update" &&
      payload.action !== "delete"
    ) {
      return json({ error: "Action must be create, update or delete" }, 400);
    }

    if (payload.action === "create") {
      const email = String(payload.email ?? "").trim().toLowerCase();
      const password = String(payload.password ?? "");
      const fullName = String(payload.full_name ?? "").trim();
      const organization = String(payload.organization ?? "").trim();
      const province = String(payload.province ?? "").trim().toUpperCase();
      const role = String(payload.role ?? "member");
      const membershipStatus = String(payload.membership_status ?? "pending");

      if (!emailPattern.test(email) || email.length > 320) {
        return json({ error: "Enter a valid email address" }, 400);
      }
      if (password.length < 10 || password.length > 128) {
        return json({ error: "Temporary password must be 10 to 128 characters" }, 400);
      }
      if (fullName.length > 160 || organization.length > 200 || province.length > 20) {
        return json({ error: "One or more profile fields are too long" }, 400);
      }
      if (!roles.has(role) || !membershipStatuses.has(membershipStatus)) {
        return json({ error: "Invalid role or membership status" }, 400);
      }

      const { data: created, error: createError } =
        await adminClient.auth.admin.createUser({
          email,
          password,
          email_confirm: true,
        });
      if (createError || !created.user) {
        return json({ error: createError?.message ?? "Could not create user" }, 400);
      }

      const createdUserId = created.user.id;
      const { data: createdProfile, error: profileError } = await adminClient
        .from("profiles")
        .update({
          email,
          full_name: fullName,
          organization,
          province,
          role,
          membership_status: membershipStatus,
        })
        .eq("id", createdUserId)
        .select("id, email, full_name, organization, province, role, membership_status")
        .single();

      if (profileError || !createdProfile) {
        await adminClient.auth.admin.deleteUser(createdUserId, false);
        return json({ error: profileError?.message ?? "Could not create portal profile" }, 400);
      }

      const { error: auditError } = await adminClient.from("audit_log").insert({
        actor_id: callerId,
        action: "member_created",
        entity_type: "profile",
        entity_id: createdUserId,
        details: { role, membership_status: membershipStatus },
      });
      if (auditError) console.error("User creation audit failed", auditError);
      return json({ user: createdProfile }, 201);
    }

    const targetUserId = String(payload.user_id ?? "");
    if (!uuidPattern.test(targetUserId)) {
      return json({ error: "A valid user ID is required" }, 400);
    }

    const { data: targetProfile, error: targetError } = await adminClient
      .from("profiles")
      .select("id, email, role, membership_status")
      .eq("id", targetUserId)
      .single();
    if (targetError || !targetProfile) {
      return json({ error: "User not found" }, 404);
    }

    const wouldRemoveActiveAdmin = (nextRole: string, nextStatus: string) =>
      targetProfile.role === "admin" &&
      targetProfile.membership_status === "active" &&
      (nextRole !== "admin" || nextStatus !== "active");

    const ensureAnotherAdmin = async () => {
      const { count, error } = await adminClient
        .from("profiles")
        .select("id", { count: "exact", head: true })
        .eq("role", "admin")
        .eq("membership_status", "active");
      if (error) throw error;
      if ((count ?? 0) <= 1) {
        throw new Error(
          "Create another active administrator before removing the last one",
        );
      }
    };

    try {
      if (payload.action === "update") {
        const email = String(payload.email ?? "")
          .trim()
          .toLowerCase();
        const fullName = String(payload.full_name ?? "").trim();
        const organization = String(payload.organization ?? "").trim();
        const province = String(payload.province ?? "")
          .trim()
          .toUpperCase();
        const role = String(payload.role ?? "");
        const membershipStatus = String(payload.membership_status ?? "");

        if (!emailPattern.test(email) || email.length > 320) {
          return json({ error: "Enter a valid email address" }, 400);
        }
        if (
          fullName.length > 160 ||
          organization.length > 200 ||
          province.length > 20
        ) {
          return json(
            { error: "One or more profile fields are too long" },
            400,
          );
        }
        if (!roles.has(role) || !membershipStatuses.has(membershipStatus)) {
          return json({ error: "Invalid role or membership status" }, 400);
        }
        if (
          targetUserId === callerId &&
          (role !== "admin" || membershipStatus !== "active")
        ) {
          return json(
            {
              error:
                "You cannot demote or suspend your own administrator account",
            },
            400,
          );
        }
        if (wouldRemoveActiveAdmin(role, membershipStatus)) {
          await ensureAnotherAdmin();
        }

        if (email !== String(targetProfile.email ?? "").toLowerCase()) {
          const { error: authUpdateError } =
            await adminClient.auth.admin.updateUserById(targetUserId, {
              email,
            });
          if (authUpdateError) throw authUpdateError;
        }

        const { data: updatedProfile, error: profileUpdateError } =
          await adminClient
            .from("profiles")
            .update({
              email,
              full_name: fullName,
              organization,
              province,
              role,
              membership_status: membershipStatus,
            })
            .eq("id", targetUserId)
            .select(
              "id, email, full_name, organization, province, role, membership_status",
            )
            .single();
        if (profileUpdateError) throw profileUpdateError;

        const { error: auditError } = await adminClient
          .from("audit_log")
          .insert({
            actor_id: callerId,
            action: "member_profile_updated",
            entity_type: "profile",
            entity_id: targetUserId,
            details: { role, membership_status: membershipStatus },
          });
        if (auditError) console.error("User update audit failed", auditError);
        return json({ user: updatedProfile });
      }

      if (targetUserId === callerId) {
        return json(
          { error: "You cannot delete your own administrator account" },
          400,
        );
      }
      if (wouldRemoveActiveAdmin("member", "suspended")) {
        await ensureAnotherAdmin();
      }

      const { data: contributions, error: contributionReadError } =
        await adminClient
          .from("contributions")
          .select("id, storage_path")
          .eq("contributor_id", targetUserId);
      if (contributionReadError) throw contributionReadError;

      const storagePaths = (contributions ?? [])
        .map((item) => String(item.storage_path ?? ""))
        .filter(Boolean);
      if (storagePaths.length > 0) {
        const { error: storageError } = await adminClient.storage
          .from("member-contributions")
          .remove(storagePaths);
        if (storageError) throw storageError;
      }

      const { error: contributionDeleteError } = await adminClient
        .from("contributions")
        .delete()
        .eq("contributor_id", targetUserId);
      if (contributionDeleteError) throw contributionDeleteError;

      const { error: userDeleteError } =
        await adminClient.auth.admin.deleteUser(targetUserId, false);
      if (userDeleteError) {
        throw new Error(
          `${userDeleteError.message}. If this user owns other Storage files, archive or reassign them first.`,
        );
      }

      const { error: auditError } = await adminClient.from("audit_log").insert({
        actor_id: callerId,
        action: "member_deleted",
        entity_type: "profile",
        entity_id: targetUserId,
        details: { contribution_count: (contributions ?? []).length },
      });
      if (auditError) console.error("User deletion audit failed", auditError);
      return json({ deleted: true, user_id: targetUserId });
    } catch (error) {
      console.error("User administration failed", error);
      return json({ error: message(error) }, 400);
    }
  }),
};
